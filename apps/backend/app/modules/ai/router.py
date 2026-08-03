import uuid

from fastapi import APIRouter, File, Query, Response, UploadFile
from sqlmodel import Field, SQLModel

from app.modules.ai import llm_settings, service
from app.modules.ai.models import (
    AIGlobalSettingsResponse,
    AIGlobalSettingsUpdate,
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    CompanyLLMSettingsResponse,
    CompanyLLMSettingsUpdate,
    ContextSummaryResponse,
    MessageResponse,
    SystemPromptResponse,
    SystemPromptUpdate,
)
from app.modules.whatsapp.service import _ensure_company_access
from app.utils.deps import AIProtected, CurrentUser, SessionDep, TokenDep

router = APIRouter()


class Message(SQLModel):
    """Generic operation result message."""

    message: str = Field(description="Human-readable status message.")


@router.post(
    "/sessions",
    status_code=201,
    response_model=ChatSessionResponse,
    summary="Create a new chat session",
    description=(
        "Start a new conversation session for the authenticated user. "
        "The session auto-expires 24 hours after creation."
    ),
)
def create_session(
    body: ChatSessionCreate,
    current_user: CurrentUser,
) -> ChatSessionResponse:
    db = service.create_session(
        user_id=current_user.id,
        title=body.title,
        system_prompt=body.system_prompt,
    )
    return ChatSessionResponse(
        id=db.id,
        title=db.title,
        system_prompt=db.system_prompt,
        is_active=db.is_active,
        created_at=db.created_at,
        expires_at=db.expires_at,
    )


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="List active chat sessions",
    description="Return the authenticated user's active chat sessions, newest first.",
)
def list_sessions(
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=50, description="Maximum number of sessions."),
    offset: int = Query(
        default=0, ge=0, le=10000, description="Number of sessions to skip."
    ),
) -> list[ChatSessionResponse]:
    sessions = service.list_sessions(user_id=current_user.id, limit=limit, offset=offset)
    return [
        ChatSessionResponse(
            id=s.id,
            title=s.title,
            system_prompt=s.system_prompt,
            is_active=s.is_active,
            created_at=s.created_at,
            expires_at=s.expires_at,
            message_count=len(s.messages) if s.messages else 0,
        )
        for s in sessions
    ]


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    summary="Get session details",
    description="Return metadata (not the messages) for a specific session.",
)
def get_session(
    session_id: uuid.UUID,
    current_user: CurrentUser,
) -> ChatSessionResponse:
    db = service.get_session(session_id=session_id, user_id=current_user.id)
    messages = service.get_session_messages(session_id=session_id, user_id=current_user.id)
    return ChatSessionResponse(
        id=db.id,
        title=db.title,
        system_prompt=db.system_prompt,
        is_active=db.is_active,
        created_at=db.created_at,
        expires_at=db.expires_at,
        message_count=len(messages),
    )


@router.get(
    "/sessions/{session_id}/context",
    response_model=ContextSummaryResponse,
    summary="Get session context summary",
    description=(
        "Return the AI-generated context summary of a session along with its "
        "full message history. The summary may be `null` when not yet generated."
    ),
)
def get_context(
    session_id: uuid.UUID,
    current_user: CurrentUser,
) -> ContextSummaryResponse:
    db = service.get_context_summary(session_id=session_id, user_id=current_user.id)
    messages = service.get_session_messages(session_id=session_id, user_id=current_user.id)
    return ContextSummaryResponse(
        session_id=session_id,
        context_summary=db.context_summary,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.get(
    "/sessions/{session_id}/system-prompt",
    response_model=SystemPromptResponse,
    summary="Get session system prompt",
    description="Return the system prompt currently configured for a session.",
)
def get_session_system_prompt(
    session_id: uuid.UUID,
    current_user: CurrentUser,
) -> SystemPromptResponse:
    system_prompt = service.get_session_system_prompt(
        session_id=session_id,
        user_id=current_user.id,
    )
    return SystemPromptResponse(
        session_id=session_id,
        system_prompt=system_prompt,
    )


@router.put(
    "/sessions/{session_id}/system-prompt",
    response_model=SystemPromptResponse,
    summary="Update session system prompt",
    description="Set a new system prompt for a session. Pass `null` or empty to clear it.",
)
def update_session_system_prompt(
    session_id: uuid.UUID,
    body: SystemPromptUpdate,
    current_user: CurrentUser,
) -> SystemPromptResponse:
    db = service.update_session_system_prompt(
        session_id=session_id,
        user_id=current_user.id,
        system_prompt=body.system_prompt,
    )
    return SystemPromptResponse(
        session_id=db.id,
        system_prompt=db.system_prompt,
    )


@router.delete(
    "/sessions/{session_id}/system-prompt",
    response_model=SystemPromptResponse,
    summary="Delete session system prompt",
    description="Remove the system prompt configured for a session.",
)
def delete_session_system_prompt(
    session_id: uuid.UUID,
    current_user: CurrentUser,
) -> SystemPromptResponse:
    db = service.delete_session_system_prompt(
        session_id=session_id,
        user_id=current_user.id,
    )
    return SystemPromptResponse(
        session_id=db.id,
        system_prompt=db.system_prompt,
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=200,
    response_model=Message,
    summary="Delete a chat session",
    description="Soft-delete a session. The session and its associated files become inactive.",
)
def delete_session(
    session_id: uuid.UUID,
    current_user: CurrentUser,
) -> Message:
    service.delete_session(session_id=session_id, user_id=current_user.id)
    return Message(message="Session deleted")


@router.post(
    "/sessions/{session_id}/chat",
    response_model=ChatResponse,
    summary="Send a message to the AI",
    description=(
        "Send a prompt within an existing session. The conversation history is "
        "preserved and included as context for the AI."
    ),
)
def chat(
    session_id: uuid.UUID,
    body: ChatRequest,
    current_user: CurrentUser,
    token: TokenDep,
) -> ChatResponse:
    response_text = service.chat(
        session_id=session_id,
        user_id=current_user.id,
        prompt=body.prompt,
        auth_token=token,
    )
    return ChatResponse(response=response_text, session_id=session_id)


@router.post(
    "/sessions/{session_id}/files",
    status_code=201,
    response_model=Message,
    summary="Upload a file to a session",
    description="Upload a file (image, PDF, etc.) associated with a chat session.",
)
def upload_file(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    file: UploadFile = File(...),  # noqa: B008
) -> Message:
    service.upload_file(
        session_id=session_id,
        user_id=current_user.id,
        file=file,
    )
    return Message(message="File uploaded")


@router.get(
    "/sessions/{session_id}/files/{file_id}",
    response_class=Response,
    summary="Download a session file",
    description=(
        "Stream a file uploaded to a chat session. Files are served from "
        "Cloudflare R2 when configured, otherwise from local storage."
    ),
)
def download_file(
    session_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: CurrentUser,
) -> Response:
    body, mime_type, filename = service.download_file(
        session_id=session_id,
        user_id=current_user.id,
        file_id=file_id,
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


@router.get(
    "/settings",
    response_model=AIGlobalSettingsResponse,
    summary="Get global AI settings",
    description=(
        "Return the global AI configuration: provider order, per-provider "
        "models, thinking power and which API keys are stored. Keys are never "
        "returned."
    ),
)
def get_global_ai_settings(
    current_user: CurrentUser,
    session: SessionDep,
    _: AIProtected,
) -> AIGlobalSettingsResponse:
    row = llm_settings.get_global_settings(session=session)
    return llm_settings.global_settings_response(row=row)


@router.put(
    "/settings",
    response_model=AIGlobalSettingsResponse,
    summary="Update global AI settings",
    description=(
        "Configure the platform AI: select the provider order, set the model "
        "per provider, choose the thinking power and store API keys. Keys are "
        "upserted per provider; pass an empty string to remove a key. This is "
        "the default used by the AI Chat and any channel without its own "
        "override."
    ),
)
def update_global_ai_settings(
    body: AIGlobalSettingsUpdate,
    current_user: CurrentUser,
    session: SessionDep,
    _: AIProtected,
) -> AIGlobalSettingsResponse:
    row = llm_settings.update_global_settings(session=session, data=body)
    return llm_settings.global_settings_response(row=row)


@router.get(
    "/companies/{company_id}/llm-settings",
    response_model=CompanyLLMSettingsResponse,
    summary="Get company LLM settings",
    description=(
        "Return the LLM provider selected for the company plus the "
        "configuration status of every provider. API keys are never returned."
    ),
)
def get_company_llm_settings(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
    _: AIProtected,
) -> CompanyLLMSettingsResponse:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    row = llm_settings.get_company_llm_settings(
        session=session, company_id=company_id
    )
    return llm_settings.company_settings_response(company_id=company_id, row=row)


@router.put(
    "/companies/{company_id}/llm-settings",
    response_model=CompanyLLMSettingsResponse,
    summary="Update company LLM settings",
    description=(
        "Select the LLM provider used by the company's AI assistant and store "
        "its API key in the database. Keys are upserted per provider; pass an "
        "empty string to remove a key. The selected provider is tried first "
        "in the failover chain, followed by the other configured providers."
    ),
)
def update_company_llm_settings(
    company_id: uuid.UUID,
    body: CompanyLLMSettingsUpdate,
    current_user: CurrentUser,
    session: SessionDep,
    _: AIProtected,
) -> CompanyLLMSettingsResponse:
    _ensure_company_access(
        session=session,
        company_id=company_id,
        current_user=current_user,
    )
    row = llm_settings.update_company_llm_settings(
        session=session,
        company_id=company_id,
        data=body,
    )
    return llm_settings.company_settings_response(company_id=company_id, row=row)
