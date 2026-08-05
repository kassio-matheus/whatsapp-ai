import asyncio
import json
import queue
import uuid

from fastapi import APIRouter, File, Header, Query, Request, UploadFile
from starlette.responses import PlainTextResponse, Response, StreamingResponse

from app.utils.deps import CurrentUser, SessionDep

from . import service
from .events import whatsapp_event_broker
from .models import (
    WhatsAppAiPrompt,
    WhatsAppAiResponse,
    WhatsAppCloudApiConnectionInfo,
    WhatsAppCloudApiConnectResponse,
    WhatsAppCloudApiCreate,
    WhatsAppCloudApiTemplateCreate,
    WhatsAppCloudApiTemplatePage,
    WhatsAppCloudApiTemplateResponse,
    WhatsAppCloudApiUpdate,
    WhatsAppContactCreate,
    WhatsAppContactResponse,
    WhatsAppContactUpdate,
    WhatsAppConversationCreate,
    WhatsAppConversationResponse,
    WhatsAppConversationUpdate,
    WhatsAppInstanceCreate,
    WhatsAppInstanceResponse,
    WhatsAppInstanceUpdate,
    WhatsAppMediaUploadResponse,
    WhatsAppMessageCreate,
    WhatsAppMessageResponse,
    WhatsAppMessageUpdate,
    WhatsAppNoteCreate,
)

router = APIRouter()
webhook_router = APIRouter()


def _integration_response(db) -> WhatsAppInstanceResponse:
    return WhatsAppInstanceResponse(
        id=db.id,
        company_id=db.company_id,
        name=db.name,
        integration_type=db.integration_type,
        adapter=db.adapter,
        phone_number=db.phone_number,
        external_account_id=db.external_account_id,
        config=db.config_json,
        credentials_configured=bool(db.credentials_json),
        is_active=db.is_active,
        created_at=db.created_at,
        updated_at=db.updated_at,
    )


def _contact_response(db) -> WhatsAppContactResponse:
    return WhatsAppContactResponse(
        id=db.id,
        company_id=db.company_id,
        instance_id=db.integration_id,
        external_id=db.external_id,
        phone_number=db.phone_number,
        name=db.name,
        profile_picture_url=db.profile_picture_url,
        is_blocked=db.is_blocked,
        metadata=db.metadata_json,
        is_active=db.is_active,
        created_at=db.created_at,
        updated_at=db.updated_at,
    )


def _conversation_response(db) -> WhatsAppConversationResponse:
    return WhatsAppConversationResponse(
        id=db.id,
        company_id=db.company_id,
        instance_id=db.integration_id,
        contact_id=db.contact_id,
        external_id=db.external_id,
        title=db.title,
        status=db.status,
        metadata=db.metadata_json,
        last_message_at=db.last_message_at,
        is_active=db.is_active,
        created_at=db.created_at,
        updated_at=db.updated_at,
    )


def _message_response(db) -> WhatsAppMessageResponse:
    return WhatsAppMessageResponse(
        id=db.id,
        company_id=db.company_id,
        instance_id=db.integration_id,
        conversation_id=db.conversation_id,
        external_id=db.external_id,
        direction=db.direction,
        message_type=db.message_type,
        content=db.content,
        media_url=db.media_url,
        status=db.status,
        metadata=db.metadata_json,
        sent_at=db.sent_at,
        is_active=db.is_active,
        created_at=db.created_at,
        updated_at=db.updated_at,
    )


def _cloud_response(
    db,
    *,
    connection,
    webhook_subscribed: bool,
) -> WhatsAppCloudApiConnectResponse:
    return WhatsAppCloudApiConnectResponse(
        instance=_integration_response(db),
        verification=WhatsAppCloudApiConnectionInfo(
            app_id=connection.app_id,
            business_account_id=connection.business_account_id,
            business_account_name=connection.business_account_name,
            phone_number_id=connection.phone_number_id,
            display_phone_number=connection.display_phone_number,
            verified_name=connection.verified_name,
            quality_rating=connection.quality_rating,
            webhook_subscribed=webhook_subscribed,
        ),
    )


@router.post(
    "/instances/cloud-api",
    status_code=201,
    response_model=WhatsAppCloudApiConnectResponse,
    summary="Connect a Meta Cloud API instance",
    description=(
        "Verify the Meta app, WABA and phone number, optionally subscribe the "
        "app to the WABA webhooks, and persist a non-coexistence instance."
    ),
)
def create_cloud_api_integration(
    data: WhatsAppCloudApiCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppCloudApiConnectResponse:
    integration, connection, webhook_subscribed = service.create_cloud_api_integration(
        session=session,
        current_user=current_user,
        data=data,
    )
    return _cloud_response(
        integration,
        connection=connection,
        webhook_subscribed=webhook_subscribed,
    )


@router.put(
    "/instances/{integration_id}/cloud-api",
    response_model=WhatsAppCloudApiConnectResponse,
    summary="Update a Meta Cloud API instance",
    description="Replace credentials and verify the Meta Cloud API instance again.",
)
def update_cloud_api_integration(
    integration_id: uuid.UUID,
    data: WhatsAppCloudApiUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppCloudApiConnectResponse:
    integration, connection, webhook_subscribed = service.update_cloud_api_integration(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
        data=data,
    )
    return _cloud_response(
        integration,
        connection=connection,
        webhook_subscribed=webhook_subscribed,
    )


@router.post(
    "/instances/{integration_id}/verify",
    response_model=WhatsAppCloudApiConnectResponse,
    summary="Verify a Meta Cloud API instance",
    description="Check the stored instance credentials and optionally re-subscribe the WABA.",
)
def verify_cloud_api_integration(
    integration_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    subscribe_to_webhooks: bool = Query(default=True),
) -> WhatsAppCloudApiConnectResponse:
    integration, connection, webhook_subscribed = service.verify_cloud_api_integration(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
        subscribe_to_webhooks=subscribe_to_webhooks,
    )
    return _cloud_response(
        integration,
        connection=connection,
        webhook_subscribed=webhook_subscribed,
    )


@router.get(
    "/instances/{integration_id}/cloud-api/templates",
    response_model=WhatsAppCloudApiTemplatePage,
    summary="List live Meta message templates",
    description=(
        "Read the current message-template catalog from the connected WABA. "
        "Only non-secret template data is returned."
    ),
)
def list_cloud_api_templates(
    integration_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=250),
    after: str | None = Query(default=None),
) -> WhatsAppCloudApiTemplatePage:
    return service.list_cloud_api_templates(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
        limit=limit,
        after=after,
    )


@router.post(
    "/instances/{integration_id}/cloud-api/templates",
    status_code=201,
    response_model=WhatsAppCloudApiTemplateResponse,
    summary="Submit a Meta message template",
    description=(
        "Submit a template to Meta's review flow. It becomes selectable in the "
        "chat only after Meta reports an APPROVED status."
    ),
)
def create_cloud_api_template(
    integration_id: uuid.UUID,
    data: WhatsAppCloudApiTemplateCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppCloudApiTemplateResponse:
    return service.create_cloud_api_template(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
        data=data,
    )


@router.delete(
    "/instances/{integration_id}/cloud-api/templates",
    status_code=204,
    summary="Delete a Meta message template",
    description=(
        "Remove a template from the connected WABA. Meta's template-management "
        "contract requires the template name; pass the Meta template ID as "
        "hsm_id to delete a single language variant instead of every variant "
        "that shares the name."
    ),
)
def delete_cloud_api_template(
    integration_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    name: str = Query(
        min_length=1,
        max_length=512,
        description="Meta template name to delete.",
    ),
    hsm_id: str | None = Query(
        default=None,
        description="Meta template ID (HSM). Restricts the delete to one variant.",
    ),
) -> None:
    service.delete_cloud_api_template(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
        template_name=name,
        hsm_id=hsm_id,
    )


@router.put(
    "/instances/{integration_id}/cloud-api/templates",
    response_model=WhatsAppCloudApiTemplateResponse,
    summary="Replace a Meta message template",
    description=(
        "Meta message templates are immutable, so an edit is delivered as a new "
        "template submitted for review while the previous one is removed. The "
        "current template name is required as previous_name; pass the Meta "
        "template ID as previous_hsm_id to replace only that language variant."
    ),
)
def replace_cloud_api_template(
    integration_id: uuid.UUID,
    data: WhatsAppCloudApiTemplateCreate,
    session: SessionDep,
    current_user: CurrentUser,
    previous_name: str = Query(
        min_length=1,
        max_length=512,
        description="Name of the template being replaced.",
    ),
    previous_hsm_id: str | None = Query(
        default=None,
        description="Meta template ID (HSM) of the variant being replaced.",
    ),
) -> WhatsAppCloudApiTemplateResponse:
    return service.replace_cloud_api_template(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
        previous_name=previous_name,
        previous_hsm_id=previous_hsm_id,
        data=data,
    )


@webhook_router.get(
    "/webhooks/meta",
    response_class=PlainTextResponse,
    summary="Verify Meta WhatsApp webhook",
    description="Public Meta webhook verification challenge endpoint.",
)
def verify_meta_webhook(
    session: SessionDep,
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    return service.verify_meta_webhook(
        session=session,
        mode=mode,
        verify_token=verify_token,
        challenge=challenge,
    )


@webhook_router.post(
    "/webhooks/meta",
    summary="Receive Meta WhatsApp webhook",
    description=(
        "Public Meta webhook receiver. The X-Hub-Signature-256 header is "
        "validated with the App Secret before messages or statuses are stored."
    ),
)
async def receive_meta_webhook(
    request: Request,
    session: SessionDep,
    signature: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict[str, int | bool]:
    return service.process_meta_webhook(
        session=session,
        raw_payload=await request.body(),
        signature_header=signature,
    )


@router.post(
    "/media/upload",
    status_code=201,
    response_model=WhatsAppMediaUploadResponse,
    summary="Upload media to storage",
    description=(
        "Upload a media file to Cloudflare R2 and return its URL so it can be "
        "used as media_url in an outbound WhatsApp message."
    ),
)
def upload_media(
    session: SessionDep,
    current_user: CurrentUser,
    company_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> WhatsAppMediaUploadResponse:
    obj = service.upload_media(
        session=session,
        current_user=current_user,
        file=file,
        company_id=company_id,
    )
    return WhatsAppMediaUploadResponse(
        key=obj.key,
        url=obj.url,
        filename=obj.filename or file.filename or "media",
        mime_type=obj.content_type,
        size_bytes=obj.size_bytes,
    )


@router.get(
    "/media/{key:path}",
    response_class=Response,
    summary="Download media from storage",
    description=(
        "Stream a media object stored in Cloudflare R2. Use the key returned "
        "by the upload endpoint or stored in message metadata."
    ),
)
def get_media(
    key: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> Response:
    body, content_type = service.download_media(key=key)
    headers = {
        "Cache-Control": "private, max-age=3600",
        "Content-Disposition": 'inline; filename="media"',
    }
    return Response(
        content=body,
        media_type=content_type or "application/octet-stream",
        headers=headers,
    )


@router.post(
    "/instances",
    status_code=201,
    response_model=WhatsAppInstanceResponse,
    summary="Create a WhatsApp instance",
    description=(
        "Register an official or unofficial instance. The adapter key is "
        "application-defined and is not tied to a specific library."
    ),
)
def create_integration(
    data: WhatsAppInstanceCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppInstanceResponse:
    return _integration_response(
        service.create_integration(
            session=session,
            current_user=current_user,
            data=data,
        )
    )


@router.get(
    "/instances",
    response_model=list[WhatsAppInstanceResponse],
    summary="List WhatsApp instances",
    description="List the WhatsApp instances accessible to the authenticated user.",
)
def list_integrations(
    session: SessionDep,
    current_user: CurrentUser,
    company_id: uuid.UUID | None = None,
) -> list[WhatsAppInstanceResponse]:
    return [
        _integration_response(item)
        for item in service.list_integrations(
            session=session,
            current_user=current_user,
            company_id=company_id,
        )
    ]


@router.get(
    "/instances/events",
    response_class=StreamingResponse,
    summary="Subscribe to WhatsApp instance events",
    description=(
        "Authenticated server-sent events for a company's WhatsApp instances, "
        "inbox changes, and message status changes. Event payloads contain only "
        "identifiers; clients fetch the relevant resource with their bearer token."
    ),
)
async def stream_instance_events(
    company_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> StreamingResponse:
    # The regular list operation centralizes the tenant-access check.
    service.list_integrations(
        session=session,
        current_user=current_user,
        company_id=company_id,
    )

    async def event_stream():
        with whatsapp_event_broker.subscribe(company_id) as subscriber:
            yield "retry: 3000\n\n"
            while True:
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 20)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                yield (
                    f"event: {event.type}\n"
                    f"data: {json.dumps(event.payload(), separators=(',', ':'))}\n\n"
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/instances/{integration_id}",
    response_model=WhatsAppInstanceResponse,
    summary="Get a WhatsApp instance",
    description="Return a single WhatsApp instance by its identifier.",
    operation_id="get_instance_by_id",
)
def get_integration(
    integration_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppInstanceResponse:
    return _integration_response(
        service.get_integration(
            session=session,
            integration_id=integration_id,
            current_user=current_user,
        )
    )


@router.put(
    "/instances/{integration_id}",
    response_model=WhatsAppInstanceResponse,
    summary="Update a WhatsApp instance",
    description="Edit an existing WhatsApp instance.",
)
def update_integration(
    integration_id: uuid.UUID,
    data: WhatsAppInstanceUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppInstanceResponse:
    return _integration_response(
        service.update_integration(
            session=session,
            integration_id=integration_id,
            current_user=current_user,
            data=data,
        )
    )


@router.delete(
    "/instances/{integration_id}",
    status_code=204,
    summary="Delete a WhatsApp instance",
    description="Soft-delete a WhatsApp instance.",
)
def delete_integration(
    integration_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    service.delete_integration(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
    )


@router.post(
    "/contacts",
    status_code=201,
    response_model=WhatsAppContactResponse,
    summary="Create a WhatsApp contact",
    description="Register a new WhatsApp contact within an instance.",
)
def create_contact(
    data: WhatsAppContactCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppContactResponse:
    return _contact_response(
        service.create_contact(
            session=session,
            current_user=current_user,
            data=data,
        )
    )


@router.get(
    "/contacts",
    response_model=list[WhatsAppContactResponse],
    summary="List WhatsApp contacts",
    description="List contacts, optionally filtered by instance or company.",
)
def list_contacts(
    session: SessionDep,
    current_user: CurrentUser,
    instance_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    limit: int = Query(
        default=50, ge=1, le=200, description="Maximum number of contacts to return."
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of contacts to skip."),
) -> list[WhatsAppContactResponse]:
    return [
        _contact_response(item)
        for item in service.list_contacts(
            session=session,
            current_user=current_user,
            integration_id=instance_id,
            company_id=company_id,
            limit=limit,
            offset=offset,
        )
    ]


@router.get(
    "/contacts/{contact_id}",
    response_model=WhatsAppContactResponse,
    summary="Get a WhatsApp contact",
    description="Return a single WhatsApp contact by its identifier.",
    operation_id="get_contact_by_id",
)
def get_contact(
    contact_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppContactResponse:
    return _contact_response(
        service.get_contact(
            session=session,
            contact_id=contact_id,
            current_user=current_user,
        )
    )


@router.put(
    "/contacts/{contact_id}",
    response_model=WhatsAppContactResponse,
    summary="Update a WhatsApp contact",
    description="Edit an existing WhatsApp contact.",
)
def update_contact(
    contact_id: uuid.UUID,
    data: WhatsAppContactUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppContactResponse:
    return _contact_response(
        service.update_contact(
            session=session,
            contact_id=contact_id,
            current_user=current_user,
            data=data,
        )
    )


@router.delete(
    "/contacts/{contact_id}",
    status_code=204,
    summary="Delete a WhatsApp contact",
    description="Soft-delete a WhatsApp contact.",
)
def delete_contact(
    contact_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    service.delete_contact(
        session=session,
        contact_id=contact_id,
        current_user=current_user,
    )


@router.post(
    "/conversations",
    status_code=201,
    response_model=WhatsAppConversationResponse,
    summary="Create a WhatsApp conversation",
    description="Start a new WhatsApp conversation linked to an instance and optionally a contact.",
)
def create_conversation(
    data: WhatsAppConversationCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppConversationResponse:
    return _conversation_response(
        service.create_conversation(
            session=session,
            current_user=current_user,
            data=data,
        )
    )


@router.get(
    "/conversations",
    response_model=list[WhatsAppConversationResponse],
    summary="List WhatsApp conversations",
    description="List conversations, optionally filtered by instance, company or contact.",
)
def list_conversations(
    session: SessionDep,
    current_user: CurrentUser,
    instance_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of conversations to return.",
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of conversations to skip."
    ),
) -> list[WhatsAppConversationResponse]:
    return [
        _conversation_response(item)
        for item in service.list_conversations(
            session=session,
            current_user=current_user,
            integration_id=instance_id,
            company_id=company_id,
            contact_id=contact_id,
            limit=limit,
            offset=offset,
        )
    ]


@router.get(
    "/conversations/{conversation_id}",
    response_model=WhatsAppConversationResponse,
    summary="Get a WhatsApp conversation",
    description="Return a single WhatsApp conversation by its identifier.",
)
def get_conversation(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppConversationResponse:
    return _conversation_response(
        service.get_conversation(
            session=session,
            conversation_id=conversation_id,
            current_user=current_user,
        )
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[WhatsAppMessageResponse],
    summary="List messages in a conversation",
    description="Return the messages of a conversation, oldest first.",
)
def list_conversation_messages(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = Query(
        default=100, ge=1, le=500, description="Maximum number of messages to return."
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of messages to skip."),
) -> list[WhatsAppMessageResponse]:
    return [
        _message_response(item)
        for item in service.list_messages(
            session=session,
            current_user=current_user,
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
        )
    ]


@router.post(
    "/conversations/{conversation_id}/note",
    status_code=201,
    response_model=WhatsAppMessageResponse,
    summary="Create an internal note",
    description=(
        "Store an internal note in a conversation timeline. Notes are visible "
        "to operators but are never delivered to the WhatsApp contact."
    ),
)
def create_conversation_note(
    conversation_id: uuid.UUID,
    data: WhatsAppNoteCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppMessageResponse:
    return _message_response(
        service.create_note(
            session=session,
            current_user=current_user,
            conversation_id=conversation_id,
            content=data.content,
        )
    )


@router.post(
    "/conversations/{conversation_id}/ai",
    status_code=201,
    response_model=WhatsAppAiResponse,
    summary="Ask the AI assistant in a conversation",
    description=(
        "Send a prompt to the AI assistant using the conversation history as "
        "context. The prompt and the AI reply are stored as internal messages "
        "that are never delivered to the WhatsApp contact."
    ),
)
def create_conversation_ai_message(
    conversation_id: uuid.UUID,
    data: WhatsAppAiPrompt,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppAiResponse:
    prompt_message, assistant_message, response_text = service.create_ai_message(
        session=session,
        current_user=current_user,
        conversation_id=conversation_id,
        prompt=data.prompt,
        actor_user_id=str(current_user.id),
    )
    return WhatsAppAiResponse(
        prompt_message=_message_response(prompt_message),
        message=_message_response(assistant_message),
        response=response_text,
    )


@router.put(
    "/conversations/{conversation_id}",
    response_model=WhatsAppConversationResponse,
    summary="Update a WhatsApp conversation",
    description="Edit an existing WhatsApp conversation.",
)
def update_conversation(
    conversation_id: uuid.UUID,
    data: WhatsAppConversationUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppConversationResponse:
    return _conversation_response(
        service.update_conversation(
            session=session,
            conversation_id=conversation_id,
            current_user=current_user,
            data=data,
        )
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    summary="Delete a WhatsApp conversation",
    description="Soft-delete a WhatsApp conversation.",
)
def delete_conversation(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    service.delete_conversation(
        session=session,
        conversation_id=conversation_id,
        current_user=current_user,
    )


@router.post(
    "/messages",
    status_code=201,
    response_model=WhatsAppMessageResponse,
    summary="Create a WhatsApp message",
    description="Register a new WhatsApp message within a conversation.",
)
def create_message(
    data: WhatsAppMessageCreate,
    session: SessionDep,
    current_user: CurrentUser
) -> WhatsAppMessageResponse:
    return _message_response(
        service.create_message(
            session=session,
            current_user=current_user,
            data=data,
        )
    )


@router.get(
    "/messages",
    response_model=list[WhatsAppMessageResponse],
    summary="List WhatsApp messages",
    description="List messages, optionally filtered by conversation, instance or company.",
)
def list_messages(
    session: SessionDep,
    current_user: CurrentUser,
    conversation_id: uuid.UUID | None = None,
    instance_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    limit: int = Query(
        default=100, ge=1, le=500, description="Maximum number of messages to return."
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of messages to skip."),
) -> list[WhatsAppMessageResponse]:
    return [
        _message_response(item)
        for item in service.list_messages(
            session=session,
            current_user=current_user,
            conversation_id=conversation_id,
            integration_id=instance_id,
            company_id=company_id,
            limit=limit,
            offset=offset,
        )
    ]


@router.get(
    "/messages/{message_id}",
    response_model=WhatsAppMessageResponse,
    summary="Get a WhatsApp message",
    description="Return a single WhatsApp message by its identifier.",
)
def get_message(
    message_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppMessageResponse:
    return _message_response(
        service.get_message(
            session=session,
            message_id=message_id,
            current_user=current_user,
        )
    )


@router.put(
    "/messages/{message_id}",
    response_model=WhatsAppMessageResponse,
    summary="Update a WhatsApp message",
    description="Edit an existing WhatsApp message (e.g. update its status).",
)
def update_message(
    message_id: uuid.UUID,
    data: WhatsAppMessageUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WhatsAppMessageResponse:
    return _message_response(
        service.update_message(
            session=session,
            message_id=message_id,
            current_user=current_user,
            data=data,
        )
    )


@router.delete(
    "/messages/{message_id}",
    status_code=204,
    summary="Delete a WhatsApp message",
    description="Soft-delete a WhatsApp message.",
)
def delete_message(
    message_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    service.delete_message(
        session=session,
        message_id=message_id,
        current_user=current_user,
    )
