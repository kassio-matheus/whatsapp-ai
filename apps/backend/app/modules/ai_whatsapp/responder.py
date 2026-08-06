"""Background worker that answers inbound WhatsApp messages with the AI.

Each reply is generated as a plain-text answer (no backend tools are exposed to
the model, so it can never push its own copy of the message) and delivered to
the customer as a normal outbound message through whichever adapter the
integration uses. The delivered message doubles as the timeline record, so the
answer appears exactly once in the thread.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from sqlalchemy import desc, text
from sqlmodel import Session, select

from app.core.db import engine
from app.modules.auth.models import User
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
    resolve_scope,
    should_auto_reply,
)

_logger = logging.getLogger(__name__)

#: Number of background workers generating WhatsApp replies.
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ai-whatsapp")

#: How long a task waits for the per-conversation lock before giving up. The
#: lock queues concurrent replies for the same chat instead of dropping them,
#: so a customer who sends two messages in a row gets both answered.
_LOCK_TIMEOUT_SECONDS = 60

_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[uuid.UUID, threading.Lock] = {}


def _conversation_lock(conversation_id: uuid.UUID) -> threading.Lock:
    """Return a per-conversation lock so we never answer a chat twice at once."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(conversation_id, threading.Lock())
    return lock


@contextmanager
def _cross_process_lock(conversation_id: uuid.UUID) -> Iterator[bool]:
    """Serialize auto-replies for the same chat across backend workers.

    Uses a *session-level* advisory lock (`pg_advisory_lock` /
    `pg_advisory_unlock`) on its own dedicated connection, held explicitly for
    as long as this context manager is open — including through the slow AI
    network call.

    A transaction-scoped lock (`pg_advisory_xact_lock`) is the wrong tool
    here: it's tied to the surrounding business transaction, and if that
    transaction is torn down mid-generation (e.g. an
    `idle_in_transaction_session_timeout` firing while we wait on the LLM),
    the lock is released early, letting a second worker answer the same
    message. A dedicated connection with an explicit lock avoids that failure
    mode, since it isn't coupled to the business transaction's lifetime.

    Yields whether the lock was actually acquired, so callers can tell the
    difference between "protected" and "running in degraded, in-process-only
    mode" (e.g. on SQLite, which has no advisory locks) instead of silently
    losing cross-process protection.
    """
    lock_key = f"whatsapp_auto_reply:{conversation_id}"
    acquired = False
    conn = engine.connect()
    try:
        try:
            conn.execute(
                text("SELECT pg_advisory_lock(hashtext(:key))"),
                {"key": lock_key},
            )
            acquired = True
        except Exception:  # noqa: BLE001 - advisory locks are PostgreSQL-only
            _logger.warning(
                "Advisory lock unavailable for conversation %s "
                "(non-PostgreSQL backend?) - falling back to in-process "
                "locking only, which does NOT protect against duplicate "
                "replies across multiple backend workers.",
                conversation_id,
            )
        yield acquired
    finally:
        if acquired:
            try:
                conn.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:key))"),
                    {"key": lock_key},
                )
            except Exception:
                _logger.exception(
                    "Failed to release advisory lock for conversation %s",
                    conversation_id,
                )
        conn.close()


def _already_answered(
    *, session: Session, conversation_id: uuid.UUID, message_id: uuid.UUID
) -> bool:
    """Whether an auto-reply was already stored for this inbound message.

    The delivered reply is a ``text`` message whose metadata carries
    ``ai_kind=auto_reply`` and ``reply_to_message_id``. Checking before
    generating makes the worker idempotent: a message that was already answered
    (e.g. because the webhook was delivered again or two workers raced) is
    never answered twice.
    """
    reference = str(message_id)
    candidates = session.exec(
        select(WhatsAppMessage)
        .where(
            WhatsAppMessage.conversation_id == conversation_id,
            WhatsAppMessage.message_type.in_(("ai", "text")),
            WhatsAppMessage.is_active == True,
        )
        .order_by(desc(WhatsAppMessage.created_at))
        .limit(50)
    ).all()
    for candidate in candidates:
        metadata = candidate.metadata_json or {}
        if (
            metadata.get("ai_kind") == "auto_reply"
            and metadata.get("reply_to_message_id") == reference
        ):
            return True
    return False


def _recent_context(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    exclude_message_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[dict[str, str]]:
    filters = [
        WhatsAppMessage.conversation_id == conversation_id,
        WhatsAppMessage.is_active == True,
        ~WhatsAppMessage.message_type.in_(INTERNAL_MESSAGE_TYPES),
        WhatsAppMessage.content.is_not(None),
    ]
    if exclude_message_id is not None:
        filters.append(WhatsAppMessage.id != exclude_message_id)
    recent = session.exec(
        select(WhatsAppMessage)
        .where(*filters)
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
        conversation = session.get(
            WhatsAppConversation, message.conversation_id)
        if conversation is None or not conversation.is_active:
            return
        integration = session.get(
            WhatsAppIntegration, conversation.integration_id)
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

        if not lock.acquire(timeout=_LOCK_TIMEOUT_SECONDS):
            return
        try:
            with _cross_process_lock(conversation.id):
                _generate_and_send(session, message, conversation, integration)
        finally:
            lock.release()


def _generate_and_send(
    session: Session,
    message: WhatsAppMessage,
    conversation: WhatsAppConversation,
    integration: WhatsAppIntegration,
) -> None:
    if _already_answered(
        session=session,
        conversation_id=conversation.id,
        message_id=message.id,
    ):
        _logger.warning(
            "Skipping duplicate AI auto-reply for message %s", message.id
        )
        return
    company = session.get(Company, conversation.company_id)
    if company is None:
        return
    company_settings = get_company_settings(
        session=session, company_id=company.id)
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

    context = _recent_context(
        session=session,
        conversation_id=conversation.id,
        exclude_message_id=message.id,
    )

    from app.modules.ai.gateway import generate_for_company

    owner = session.get(User, company.owner_id) if company.owner_id else None

    try:
        result = generate_for_company(
            session=session,
            company=company,
            owner=owner,
            prompt=(
                f'The customer just sent: "{message.content or ""}". '
                "Write the reply to send to the customer."
            ),
            context=context,
            system_prompt=system_prompt,
            actor_user_id=str(company.owner_id),
            allowed_tools=[],
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
        _logger.warning(
            "AI auto-reply returned an empty message for %s", message.id
        )
        whatsapp_service.create_ai_failure_note(
            session=session,
            conversation=conversation,
            reason="AI returned an empty reply",
            reply_to_message=message,
        )
        return

    # Second idempotency check right before delivery: generation can take a few
    # seconds, and with multiple backend workers another process may have
    # already delivered the reply in the meantime.
    if _already_answered(
        session=session,
        conversation_id=conversation.id,
        message_id=message.id,
    ):
        _logger.warning(
            "Skipping duplicate AI auto-reply for message %s (delivered elsewhere)",
            message.id,
        )
        return

    reply_metadata = {"mcp_scope": scope.as_dict()}
    whatsapp_service.create_ai_reply_message(
        session=session,
        conversation=conversation,
        content=response_text,
        reply_to_message=message,
        metadata=reply_metadata,
    )
