"""HTTP API for the WhatsApp AI auto-responder settings and tools.

The router is registered behind ``/whatsapp/ai`` and requires authentication.
Everything exposed here configures how the AI assistant behaves in the inbox:
company-level activation, trusted owner numbers, the MCP tool whitelist for
contacts and per-conversation overrides.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Response, UploadFile
from sqlmodel import Field, SQLModel

from app.modules.ai import documents as ai_documents
from app.modules.ai.mcp import list_mcp_tools
from app.modules.ai.models import (
    AIDocumentResponse,
    CompanyKnowledgeResponse,
    CompanyKnowledgeUpdate,
)
from app.modules.ai_whatsapp import service
from app.modules.ai_whatsapp.models import (
    ConversationAISettingsResponse,
    ConversationAISettingsUpdate,
    McpToolInfo,
    McpToolsPage,
    WhatsAppAISettings,
    WhatsAppAISettingsResponse,
    WhatsAppAISettingsUpdate,
)
from app.modules.whatsapp.service import (
    _ensure_company_access,
    get_conversation,
)
from app.utils.deps import CurrentUser, SessionDep

router = APIRouter()


class Message(SQLModel):
    """Generic operation result message."""

    message: str = Field(description="Human-readable status message.")


def _settings_response(
    settings: WhatsAppAISettings | None, company_id: uuid.UUID
) -> WhatsAppAISettingsResponse:
    if settings is None:
        return WhatsAppAISettingsResponse(
            company_id=company_id,
            enabled=False,
            system_prompt=None,
            trusted_phone_numbers=[],
            allowed_contact_tools=[],
            reply_cooldown_seconds=20,
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
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
    return _settings_response(settings, company_id)


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
    return _settings_response(settings, company_id)


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
                required=tool.get("required") or [],
                requires=tool.get("requires") or [],
            )
            for tool in list_mcp_tools()
        ],
        allowed=list(settings.allowed_contact_tools) if settings else [],
    )


def _document_response(document) -> AIDocumentResponse:
    return AIDocumentResponse(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        extraction_status=document.extraction_status,
        created_at=document.created_at,
    )


def _knowledge_response(
    *, session, company_id: uuid.UUID
) -> CompanyKnowledgeResponse:
    profile = ai_documents.get_company_profile(
        session=session, company_id=company_id
    )
    documents = ai_documents.list_company_documents(company_id=company_id)
    return CompanyKnowledgeResponse(
        company_id=company_id,
        company_info=profile.company_info if profile else None,
        documents=[_document_response(document) for document in documents],
    )


@router.get(
    "/companies/{company_id}/ai/knowledge",
    response_model=CompanyKnowledgeResponse,
    summary="Get company AI knowledge",
    description=(
        "Return the company information and knowledge documents that are "
        "injected into the AI assistant's system prompt."
    ),
)
def get_company_knowledge(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> CompanyKnowledgeResponse:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    return _knowledge_response(session=session, company_id=company_id)


@router.put(
    "/companies/{company_id}/ai/knowledge",
    response_model=CompanyKnowledgeResponse,
    summary="Update company AI knowledge",
    description=(
        "Set the company information injected into the AI assistant's system "
        "prompt. Pass `null` or empty to clear it."
    ),
)
def update_company_knowledge(
    company_id: uuid.UUID,
    body: CompanyKnowledgeUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> CompanyKnowledgeResponse:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    ai_documents.update_company_profile(
        session=session,
        company_id=company_id,
        company_info=body.company_info,
    )
    return _knowledge_response(session=session, company_id=company_id)


@router.get(
    "/companies/{company_id}/ai/documents",
    response_model=list[AIDocumentResponse],
    summary="List company AI documents",
    description="Return the documents the company uploaded as AI knowledge.",
)
def list_company_ai_documents(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> list[AIDocumentResponse]:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    documents = ai_documents.list_company_documents(company_id=company_id)
    return [_document_response(document) for document in documents]


@router.post(
    "/companies/{company_id}/ai/documents",
    status_code=201,
    response_model=AIDocumentResponse,
    summary="Upload a company AI document",
    description=(
        "Upload a knowledge document (PDF, image or text) for the company AI "
        "assistant. Its text is extracted and injected into the system prompt."
    ),
)
def upload_document(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),  # noqa: B008
) -> AIDocumentResponse:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    document = ai_documents.upload_company_document(
        company_id=company_id,
        uploader_id=current_user.id,
        file=file,
    )
    return _document_response(document)


@router.get(
    "/companies/{company_id}/ai/documents/{document_id}",
    response_class=Response,
    summary="Download a company AI document",
    description=(
        "Stream a knowledge document. Files are served from Cloudflare R2 "
        "when configured, otherwise from local storage."
    ),
)
def download_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> Response:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    body, mime_type, filename = ai_documents.download_company_document(
        company_id=company_id,
        document_id=document_id,
    )
    headers = {
        "Cache-Control": "private, max-age=3600",
        "Content-Disposition": f'inline; filename="{filename}"',
    }
    return Response(
        content=body,
        media_type=mime_type or "application/octet-stream",
        headers=headers,
    )


@router.delete(
    "/companies/{company_id}/ai/documents/{document_id}",
    status_code=200,
    response_model=Message,
    summary="Delete a company AI document",
    description="Remove a knowledge document and its stored blob.",
)
def delete_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> Message:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    ai_documents.delete_company_document(
        company_id=company_id,
        document_id=document_id,
    )
    return Message(message="Document deleted")


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
