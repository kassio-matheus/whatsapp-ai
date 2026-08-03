"""Background worker that answers inbound WhatsApp messages with the AI.

Each reply is generated with an MCP session whose tool set depends on who sent
the message (owner/trusted number -> every tool, contact -> whitelist). Replies
are stored as an internal AI draft and delivered to the customer as a normal
outbound message through whichever adapter the integration uses.
"""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import desc
from sqlmodel import Session, select

from app.core.db import engine
from app.modules.companies.models import Company
from app.modules.whatsapp import service as whatsapp_service
from app.modules.whatsapp.models import (
    INTERNAL_MESSAGE_TYPES,
    MessageDirection,
    WhatsAppConversation,
    WhatsAppIntegration,
    WhatsAppMessage,
)

from .service import (
    DEFAULT_AUTO_REPLY_SYSTEM_PROMPT,
    get_company_settings,
    get_conversation_ai_settings,
    owner_access_token,
    resolve_scope,
    should_auto_reply,
)

_logger = logging.getLogger(__name__)

#: Number of background workers generating WhatsApp replies.
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ai-whatsapp")

_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[uuid.UUID, threading.Lock] = {}


def _conversation_lock(conversation_id: uuid.UUID) -> threading.Lock:
    """Return a per-conversation lock so we never answer a chat twice at once."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(conversation_id, threading.Lock())
    return lock


def _recent_context(
    *, session: Session, conversation_id: uuid.UUID, limit: int = 30
) -> list[dict[str, str]]:
    recent = session.exec(
        select(WhatsAppMessage)
        .where(
            WhatsAppMessage.conversation_id == conversation_id,
            WhatsAppMessage.is_active == True,
            ~WhatsAppMessage.message_type.in_(INTERNAL_MESSAGE_TYPES),
            WhatsAppMessage.content.is_not(None),
        )
        .order_by(desc(WhatsAppMessage.created_at))
        .limit(limit)
    ).all()
    history = list(reversed(recent))
    return [
        {
            "role": "user"
            if m.direction == MessageDirection.INBOUND.value
            else "assistant",
            "content": m.content or "",
        }
        for m in history
    ]


def schedule(session: Session, message_id: uuid.UUID) -> bool:
    """Cheap pre-check, then hand the work to the background executor."""
    message = session.get(WhatsAppMessage, message_id)
    if message is None or not message.is_active:
        return False
    conversation = session.get(WhatsAppConversation, message.conversation_id)
    if conversation is None or not conversation.is_active:
        return False
    integration = session.get(WhatsAppIntegration, conversation.integration_id)
    if integration is None:
        return False
    if not should_auto_reply(
        session=session,
        message=message,
        conversation=conversation,
        integration=integration,
    ):
        return False
    _EXECUTOR.submit(process, message_id)
    return True


def process(message_id: uuid.UUID) -> None:
    try:
        _process(message_id)
    except Exception:
        _logger.exception("AI auto-reply failed for message %s", message_id)


def _process(message_id: uuid.UUID) -> None:
    with Session(engine) as session:
        message = session.get(WhatsAppMessage, message_id)
        if message is None or not message.is_active:
            return
        conversation = session.get(WhatsAppConversation, message.conversation_id)
        if conversation is None or not conversation.is_active:
            return
        integration = session.get(WhatsAppIntegration, conversation.integration_id)
        if integration is None:
            return
        if not should_auto_reply(
            session=session,
            message=message,
            conversation=conversation,
            integration=integration,
        ):
            return

        lock = _conversation_lock(conversation.id)
        if not lock.acquire(blocking=False):
            return
        try:
            _generate_and_send(session, message, conversation, integration)
        finally:
            lock.release()


def _generate_and_send(
    session: Session,
    message: WhatsAppMessage,
    conversation: WhatsAppConversation,
    integration: WhatsAppIntegration,
) -> None:
    company = session.get(Company, conversation.company_id)
    if company is None:
        return
    company_settings = get_company_settings(session=session, company_id=company.id)
    conversation_setting = get_conversation_ai_settings(
        session=session, conversation_id=conversation.id
    )

    contact_phone = None
    if conversation.contact_id is not None:
        from app.modules.whatsapp.models import WhatsAppContact

        contact = session.get(WhatsAppContact, conversation.contact_id)
        if contact is not None:
            contact_phone = contact.phone_number

    scope = resolve_scope(
        session=session,
        integration=integration,
        conversation=conversation,
        contact_phone=contact_phone,
        company=company,
    )

    parts = [DEFAULT_AUTO_REPLY_SYSTEM_PROMPT]
    if company_settings is not None and company_settings.system_prompt:
        parts.append(company_settings.system_prompt)
    if conversation_setting is not None and conversation_setting.system_prompt:
        parts.append(conversation_setting.system_prompt)
    system_prompt = "\n\n".join(parts)

    context = _recent_context(session=session, conversation_id=conversation.id)

    from app.modules.ai.llm_settings import build_llm_for_company

    try:
        result = build_llm_for_company(
            session=session,
            company_id=company.id,
        ).generate(
            prompt=message.content or "",
            context=context,
            system_prompt=system_prompt,
            auth_token=owner_access_token(company),
            allowed_tools=scope.allowed_tools,
        )
    except Exception as exc:  # noqa: BLE001 - deliver a graceful failure note
        _logger.warning("AI auto-reply generation failed: %s", exc)
        whatsapp_service.create_ai_failure_note(
            session=session,
            conversation=conversation,
            reason=str(exc),
            reply_to_message=message,
        )
        return

    response_text = result.response.strip()
    if not response_text:
        return

    draft_metadata = {
        "ai_kind": "auto_reply",
        "reply_to_message_id": str(message.id),
        "mcp_scope": scope.as_dict(),
    }
    whatsapp_service.create_internal_ai_draft(
        session=session,
        conversation=conversation,
        content=response_text,
        metadata=draft_metadata,
    )
    whatsapp_service.create_ai_reply_message(
        session=session,
        conversation=conversation,
        content=response_text,
        reply_to_message=message,
    )
