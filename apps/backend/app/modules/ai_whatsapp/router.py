"""HTTP API for the WhatsApp AI auto-responder settings and tools.

The router is registered behind ``/whatsapp/ai`` and requires authentication.
Everything exposed here configures how the AI assistant behaves in the inbox:
company-level activation, trusted owner numbers, the MCP tool whitelist for
contacts and per-conversation overrides.
"""

import uuid

from fastapi import APIRouter

from app.modules.ai.mcp import list_mcp_tools
from app.modules.ai_whatsapp import service
from app.modules.ai_whatsapp.models import (
    ConversationAISettingsResponse,
    ConversationAISettingsUpdate,
    McpToolInfo,
    McpToolsPage,
    WhatsAppAISettingsResponse,
    WhatsAppAISettingsUpdate,
)
from app.modules.whatsapp.service import (
    _ensure_company_access,
    get_conversation,
)
from app.utils.deps import CurrentUser, SessionDep

router = APIRouter()


def _settings_response(settings) -> WhatsAppAISettingsResponse:
    return WhatsAppAISettingsResponse(
        company_id=settings.company_id,
        enabled=settings.enabled,
        system_prompt=settings.system_prompt,
        trusted_phone_numbers=list(settings.trusted_phone_numbers),
        allowed_contact_tools=list(settings.allowed_contact_tools),
        reply_cooldown_seconds=settings.reply_cooldown_seconds,
        updated_at=settings.updated_at,
    )


def _conversation_response(setting) -> ConversationAISettingsResponse:
    return ConversationAISettingsResponse(
        conversation_id=setting.conversation_id,
        enabled=setting.enabled,
        system_prompt=setting.system_prompt,
    )


@router.get(
    "/companies/{company_id}/ai/settings",
    response_model=WhatsAppAISettingsResponse,
    summary="Get company WhatsApp AI settings",
    description=(
        "Return the company-level configuration for the WhatsApp AI "
        "auto-responder. Missing settings report their defaults."
    ),
)
def get_company_ai_settings(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> WhatsAppAISettingsResponse:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    settings = service.get_company_settings(
        session=session, company_id=company_id
    )
    return _settings_response(settings)


@router.put(
    "/companies/{company_id}/ai/settings",
    response_model=WhatsAppAISettingsResponse,
    summary="Update company WhatsApp AI settings",
    description=(
        "Update the company-level configuration for the WhatsApp AI "
        "auto-responder: global switch, owner phone numbers, the contact MCP "
        "tool whitelist, the system prompt and the reply cooldown."
    ),
)
def update_company_ai_settings(
    company_id: uuid.UUID,
    body: WhatsAppAISettingsUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> WhatsAppAISettingsResponse:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    settings = service.update_company_settings(
        session=session,
        company_id=company_id,
        data=body,
    )
    return _settings_response(settings)


@router.get(
    "/companies/{company_id}/ai/mcp-tools",
    response_model=McpToolsPage,
    summary="List MCP tools available to WhatsApp AI",
    description=(
        "Return every MCP tool the backend exposes plus the names currently "
        "allowed for regular WhatsApp contacts, so the owner can build the "
        "whitelist."
    ),
)
def list_company_ai_mcp_tools(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> McpToolsPage:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    settings = service.get_company_settings(
        session=session, company_id=company_id
    )
    return McpToolsPage(
        tools=[
            McpToolInfo(
                name=tool["name"],
                method=tool["method"],
                path=tool["path"],
                summary=tool["summary"],
                description=tool["description"],
                requires_auth=tool["requires_auth"],
            )
            for tool in list_mcp_tools()
        ],
        allowed=list(settings.allowed_contact_tools) if settings else [],
    )


@router.get(
    "/conversations/{conversation_id}/ai/settings",
    response_model=ConversationAISettingsResponse,
    summary="Get per-conversation AI settings",
    description=(
        "Return the AI override for a conversation. A `null` enabled value "
        "means the conversation follows the company-level setting."
    ),
)
def get_conversation_ai_settings(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> ConversationAISettingsResponse:
    get_conversation(
        session=session,
        conversation_id=conversation_id,
        current_user=current_user,
    )
    setting = service.get_conversation_ai_settings(
        session=session, conversation_id=conversation_id
    )
    if setting is None:
        return ConversationAISettingsResponse(
            conversation_id=conversation_id,
            enabled=None,
            system_prompt=None,
        )
    return _conversation_response(setting)


@router.put(
    "/conversations/{conversation_id}/ai/settings",
    response_model=ConversationAISettingsResponse,
    summary="Update per-conversation AI settings",
    description=(
        "Force the AI on or off for a conversation, or return to following the "
        "company setting by passing `enabled` as `null`. A per-conversation "
        "system prompt can be set here as well."
    ),
)
def update_conversation_ai_settings(
    conversation_id: uuid.UUID,
    body: ConversationAISettingsUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> ConversationAISettingsResponse:
    get_conversation(
        session=session,
        conversation_id=conversation_id,
        current_user=current_user,
    )
    setting = service.update_conversation_ai_settings(
        session=session,
        conversation_id=conversation_id,
        data=body,
    )
    return _conversation_response(setting)
