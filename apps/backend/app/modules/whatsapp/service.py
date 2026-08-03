import datetime
import hmac
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, cast

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import asc, desc
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.r2 import R2Error, R2Object, r2
from app.modules.auth.models import User
from app.modules.companies.models import Company

logger = logging.getLogger(__name__)

from .adapters import whatsapp_adapter_registry
from .cloud_api import (
    META_CLOUD_API_ADAPTER,
    CloudApiConnectionInfo,
    MediaDownload,
    MetaCloudApiClient,
    MetaCloudApiError,
    verify_webhook_signature,
)
from .events import whatsapp_event_broker
from .models import (
    INTERNAL_MESSAGE_TYPES,
    IntegrationType,
    MessageDirection,
    MessageStatus,
    WhatsAppCloudApiCreate,
    WhatsAppCloudApiCredentials,
    WhatsAppCloudApiTemplateCreate,
    WhatsAppCloudApiTemplatePage,
    WhatsAppCloudApiTemplateResponse,
    WhatsAppCloudApiUpdate,
    WhatsAppContact,
    WhatsAppContactCreate,
    WhatsAppContactUpdate,
    WhatsAppConversation,
    WhatsAppConversationCreate,
    WhatsAppConversationUpdate,
    WhatsAppIntegration,
    WhatsAppIntegrationCreate,
    WhatsAppIntegrationUpdate,
    WhatsAppMessage,
    WhatsAppMessageCreate,
    WhatsAppMessageUpdate,
)
from .phone_numbers import format_phone_number_for_meta


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A WhatsApp resource with the same unique fields already exists",
        ) from exc


_MEDIA_EXTENSION = re.compile(r"\.([a-zA-Z0-9]{1,10})$")


def _safe_filename(filename: str | None) -> str:
    name = Path(filename or "media").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:120] or "media"


def _media_key(*, company_id: uuid.UUID, kind: str, filename: str) -> str:
    safe_name = _safe_filename(filename)
    return f"whatsapp/{company_id}/{kind}/{uuid.uuid4()}/{safe_name}"


def _extension_for(mime_type: str | None) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/amr": ".amr",
        "video/mp4": ".mp4",
        "video/3gpp": ".3gp",
        "application/pdf": ".pdf",
    }.get((mime_type or "").split(";")[0].strip().lower(), "")


def _ensure_r2() -> None:
    if not r2.configured:
        raise HTTPException(
            status_code=503,
            detail="Media storage (Cloudflare R2) is not configured",
        )


def upload_media(
    *,
    session: Session,
    current_user: User,
    file: UploadFile,
    company_id: uuid.UUID | None = None,
) -> R2Object:
    """Upload a file to R2 and return its object metadata."""
    _ensure_r2()
    company = _ensure_company_access(
        session=session,
        company_id=company_id or (current_user.company_id or uuid.UUID(int=0)),
        current_user=current_user,
    )
    filename = _safe_filename(file.filename)
    content_type = file.content_type or "application/octet-stream"
    extension = _extension_for(content_type)
    size = 0
    chunk_buffer = bytearray()
    try:
        while chunk := file.file.read(64 * 1024):
            size += len(chunk)
            if size > settings.MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File is too large")
            chunk_buffer.extend(chunk)
    finally:
        file.file.close()

    key = _media_key(
        company_id=company.id,
        kind="uploads",
        filename=f"{Path(filename).stem or 'media'}{extension}",
    )
    return r2.put_object(key=key, data=bytes(chunk_buffer), content_type=content_type)


def download_media(*, key: str) -> tuple[bytes, str | None]:
    """Fetch a media object from R2 as raw bytes."""
    _ensure_r2()
    try:
        body, content_type = r2.get_object(key=key)
    except Exception as exc:
        raise HTTPException(
            status_code=404 if getattr(exc, "status_code", None) == 404 else 502,
            detail="Could not retrieve media object",
        ) from exc
    return body, content_type


def _ensure_company_access(
    *, session: Session, company_id: uuid.UUID, current_user: User
) -> Company:
    company = session.get(Company, company_id)
    if not company or not company.is_active:
        raise HTTPException(status_code=404, detail="Company not found")

    has_access = (
        company.owner_id == current_user.id
        if current_user.is_super_admin
        else current_user.company_id == company.id
    )
    if not has_access:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _accessible_company_ids(
    *,
    session: Session,
    current_user: User,
    company_id: uuid.UUID | None = None,
) -> list[uuid.UUID]:
    if company_id is not None:
        return [
            _ensure_company_access(
                session=session,
                company_id=company_id,
                current_user=current_user,
            ).id
        ]

    if current_user.is_super_admin:
        statement = select(Company.id).where(
            Company.owner_id == current_user.id,
            Company.is_active == True,
        )
        return list(session.exec(statement).all())

    if current_user.company_id is None:
        return []
    try:
        return [
            _ensure_company_access(
                session=session,
                company_id=current_user.company_id,
                current_user=current_user,
            ).id
        ]
    except HTTPException:
        return []


def _get_integration(
    *, session: Session, integration_id: uuid.UUID, current_user: User
) -> WhatsAppIntegration:
    integration = session.get(WhatsAppIntegration, integration_id)
    if not integration or not integration.is_active:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
    _ensure_company_access(
        session=session,
        company_id=integration.company_id,
        current_user=current_user,
    )
    return integration


def _get_contact(
    *, session: Session, contact_id: uuid.UUID, current_user: User
) -> WhatsAppContact:
    contact = session.get(WhatsAppContact, contact_id)
    if not contact or not contact.is_active:
        raise HTTPException(status_code=404, detail="WhatsApp contact not found")
    integration = _get_integration(
        session=session,
        integration_id=contact.integration_id,
        current_user=current_user,
    )
    if contact.company_id != integration.company_id:
        raise HTTPException(status_code=404, detail="WhatsApp contact not found")
    return contact


def _get_conversation(
    *, session: Session, conversation_id: uuid.UUID, current_user: User
) -> WhatsAppConversation:
    conversation = session.get(WhatsAppConversation, conversation_id)
    if not conversation or not conversation.is_active:
        raise HTTPException(status_code=404, detail="WhatsApp conversation not found")
    integration = _get_integration(
        session=session,
        integration_id=conversation.integration_id,
        current_user=current_user,
    )
    if conversation.company_id != integration.company_id:
        raise HTTPException(status_code=404, detail="WhatsApp conversation not found")
    return conversation


def _get_message(
    *, session: Session, message_id: uuid.UUID, current_user: User
) -> WhatsAppMessage:
    message = session.get(WhatsAppMessage, message_id)
    if not message or not message.is_active:
        raise HTTPException(status_code=404, detail="WhatsApp message not found")
    conversation = _get_conversation(
        session=session,
        conversation_id=message.conversation_id,
        current_user=current_user,
    )
    if (
        message.company_id != conversation.company_id
        or message.integration_id != conversation.integration_id
    ):
        raise HTTPException(status_code=404, detail="WhatsApp message not found")
    return message


def list_integrations(
    *,
    session: Session,
    current_user: User,
    company_id: uuid.UUID | None = None,
) -> list[WhatsAppIntegration]:
    company_ids = _accessible_company_ids(
        session=session,
        current_user=current_user,
        company_id=company_id,
    )
    statement = (
        select(WhatsAppIntegration)
        .where(
            WhatsAppIntegration.company_id.in_(company_ids),
            WhatsAppIntegration.is_active == True,
        )
        .order_by(desc(WhatsAppIntegration.created_at))
    )
    return list(session.exec(statement).all())


def create_integration(
    *,
    session: Session,
    current_user: User,
    data: WhatsAppIntegrationCreate,
) -> WhatsAppIntegration:
    if data.adapter == META_CLOUD_API_ADAPTER:
        raise HTTPException(
            status_code=422,
            detail=(
                "Use POST /whatsapp/instances/cloud-api so the Meta "
                "credentials and phone number are verified"
            ),
        )
    _ensure_company_access(
        session=session,
        company_id=data.company_id,
        current_user=current_user,
    )
    integration = WhatsAppIntegration(
        company_id=data.company_id,
        name=data.name,
        integration_type=data.integration_type.value,
        adapter=data.adapter,
        phone_number=data.phone_number,
        external_account_id=data.external_account_id,
        credentials_json=data.credentials,
        config_json=data.config,
    )
    session.add(integration)
    _commit(session)
    session.refresh(integration)
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="instance.created",
        instance_id=integration.id,
    )
    return integration


def _cloud_credentials(
    integration: WhatsAppIntegration,
) -> WhatsAppCloudApiCredentials:
    try:
        return WhatsAppCloudApiCredentials.model_validate(integration.credentials_json)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="The stored Meta Cloud API credentials are incomplete or invalid",
        ) from exc


def _cloud_error(exc: MetaCloudApiError) -> HTTPException:
    status_code = 502 if exc.status_code in {None, 502} else 422
    return HTTPException(
        status_code=status_code,
        detail=f"Meta Cloud API connection failed: {exc}",
    )


def _cloud_config(
    *,
    credentials: WhatsAppCloudApiCredentials,
    connection: CloudApiConnectionInfo,
    webhook_subscribed: bool,
) -> dict[str, object]:
    return {
        "provider": "meta",
        "api_version": credentials.api_version,
        "business_account_id": connection.business_account_id,
        "phone_number_id": connection.phone_number_id,
        "business_account_name": connection.business_account_name,
        "verified_name": connection.verified_name,
        "quality_rating": connection.quality_rating,
        "coexistence": False,
        "webhook_subscribed": webhook_subscribed,
    }


def _verify_cloud_connection(
    *,
    credentials: WhatsAppCloudApiCredentials,
    subscribe_to_webhooks: bool,
) -> tuple[CloudApiConnectionInfo, bool]:
    client = MetaCloudApiClient(credentials)
    try:
        connection = client.verify_connection()
        webhook_subscribed = (
            client.subscribe_to_business_account() if subscribe_to_webhooks else False
        )
    except MetaCloudApiError as exc:
        raise _cloud_error(exc) from exc
    return connection, webhook_subscribed


def create_cloud_api_integration(
    *,
    session: Session,
    current_user: User,
    data: WhatsAppCloudApiCreate,
) -> tuple[WhatsAppIntegration, CloudApiConnectionInfo, bool]:
    _ensure_company_access(
        session=session,
        company_id=data.company_id,
        current_user=current_user,
    )
    connection, webhook_subscribed = _verify_cloud_connection(
        credentials=data.credentials,
        subscribe_to_webhooks=data.subscribe_to_webhooks,
    )
    integration = WhatsAppIntegration(
        company_id=data.company_id,
        name=data.name,
        integration_type=IntegrationType.OFFICIAL.value,
        adapter=META_CLOUD_API_ADAPTER,
        phone_number=connection.display_phone_number,
        external_account_id=connection.business_account_id,
        credentials_json=data.credentials.model_dump(),
        config_json=_cloud_config(
            credentials=data.credentials,
            connection=connection,
            webhook_subscribed=webhook_subscribed,
        ),
    )
    session.add(integration)
    _commit(session)
    session.refresh(integration)
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="instance.connected",
        instance_id=integration.id,
    )
    return integration, connection, webhook_subscribed


def update_cloud_api_integration(
    *,
    session: Session,
    integration_id: uuid.UUID,
    current_user: User,
    data: WhatsAppCloudApiUpdate,
) -> tuple[WhatsAppIntegration, CloudApiConnectionInfo, bool]:
    integration = _get_integration(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
    )
    if integration.adapter != META_CLOUD_API_ADAPTER:
        raise HTTPException(
            status_code=422,
            detail="The selected integration is not a Meta WhatsApp Cloud API connection",
        )
    connection, webhook_subscribed = _verify_cloud_connection(
        credentials=data.credentials,
        subscribe_to_webhooks=data.subscribe_to_webhooks,
    )
    if data.name is not None:
        integration.name = data.name
    integration.integration_type = IntegrationType.OFFICIAL.value
    integration.phone_number = connection.display_phone_number
    integration.external_account_id = connection.business_account_id
    integration.credentials_json = data.credentials.model_dump()
    integration.config_json = _cloud_config(
        credentials=data.credentials,
        connection=connection,
        webhook_subscribed=webhook_subscribed,
    )
    integration.updated_at = _now()
    session.add(integration)
    _commit(session)
    session.refresh(integration)
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="instance.updated",
        instance_id=integration.id,
    )
    return integration, connection, webhook_subscribed


def verify_cloud_api_integration(
    *,
    session: Session,
    integration_id: uuid.UUID,
    current_user: User,
    subscribe_to_webhooks: bool = True,
) -> tuple[WhatsAppIntegration, CloudApiConnectionInfo, bool]:
    integration = _get_integration(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
    )
    if integration.adapter != META_CLOUD_API_ADAPTER:
        raise HTTPException(
            status_code=422,
            detail="The selected integration is not a Meta WhatsApp Cloud API connection",
        )
    credentials = _cloud_credentials(integration)
    connection, webhook_subscribed = _verify_cloud_connection(
        credentials=credentials,
        subscribe_to_webhooks=subscribe_to_webhooks,
    )
    integration.phone_number = connection.display_phone_number
    integration.external_account_id = connection.business_account_id
    integration.config_json = _cloud_config(
        credentials=credentials,
        connection=connection,
        webhook_subscribed=webhook_subscribed,
    )
    integration.updated_at = _now()
    session.add(integration)
    _commit(session)
    session.refresh(integration)
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="instance.verified",
        instance_id=integration.id,
    )
    return integration, connection, webhook_subscribed


def _cloud_template_integration(
    *, session: Session, integration_id: uuid.UUID, current_user: User
) -> WhatsAppIntegration:
    integration = _get_integration(
        session=session, integration_id=integration_id, current_user=current_user
    )
    if integration.adapter != META_CLOUD_API_ADAPTER:
        raise HTTPException(
            status_code=422,
            detail="Templates are available only for a Meta WhatsApp Cloud API connection",
        )
    return integration


def _template_page_response(page) -> WhatsAppCloudApiTemplatePage:
    return WhatsAppCloudApiTemplatePage(
        data=[
            WhatsAppCloudApiTemplateResponse(
                id=item.id,
                name=item.name,
                language=item.language,
                status=item.status,
                category=item.category,
                components=item.components,
                quality_score=item.quality_score,
                rejected_reason=item.rejected_reason,
            )
            for item in page.data
        ],
        next_cursor=page.next_cursor,
    )


def list_cloud_api_templates(
    *,
    session: Session,
    integration_id: uuid.UUID,
    current_user: User,
    limit: int = 100,
    after: str | None = None,
) -> WhatsAppCloudApiTemplatePage:
    """Return a live, access-controlled page from Meta's template catalog."""

    integration = _cloud_template_integration(
        session=session, integration_id=integration_id, current_user=current_user
    )
    try:
        page = MetaCloudApiClient(
            _cloud_credentials(integration)
        ).get_message_templates(limit=limit, after=after)
    except MetaCloudApiError as exc:
        raise _cloud_error(exc) from exc
    return _template_page_response(page)


def create_cloud_api_template(
    *,
    session: Session,
    integration_id: uuid.UUID,
    current_user: User,
    data: WhatsAppCloudApiTemplateCreate,
) -> WhatsAppCloudApiTemplateResponse:
    """Submit a template for Meta review and fan out the catalog change."""

    integration = _cloud_template_integration(
        session=session, integration_id=integration_id, current_user=current_user
    )
    payload = data.model_dump()
    payload["language"] = payload["language"].replace("-", "_")
    payload["category"] = payload["category"].upper()
    try:
        response = MetaCloudApiClient(
            _cloud_credentials(integration)
        ).create_message_template(payload)
    except MetaCloudApiError as exc:
        raise _cloud_error(exc) from exc
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="template.created",
        instance_id=integration.id,
    )
    return WhatsAppCloudApiTemplateResponse(
        id=str(response.get("id") or ""),
        name=data.name,
        language=payload["language"],
        status=str(response.get("status") or "PENDING"),
        category=str(response.get("category") or payload["category"]),
        components=data.components,
        quality_score=None,
        rejected_reason=None,
    )


def delete_cloud_api_template(
    *,
    session: Session,
    integration_id: uuid.UUID,
    current_user: User,
    template_name: str,
    hsm_id: str | None = None,
) -> None:
    """Delete a template from the connected WABA and fan out the catalog change."""

    integration = _cloud_template_integration(
        session=session, integration_id=integration_id, current_user=current_user
    )
    try:
        deleted = MetaCloudApiClient(_cloud_credentials(integration)).delete_message_template(
            name=template_name, hsm_id=hsm_id
        )
    except MetaCloudApiError as exc:
        raise _cloud_error(exc) from exc
    if not deleted:
        raise HTTPException(
            status_code=502,
            detail="Meta did not confirm the template deletion",
        )
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="template.deleted",
        instance_id=integration.id,
    )


def replace_cloud_api_template(
    *,
    session: Session,
    integration_id: uuid.UUID,
    current_user: User,
    previous_name: str,
    previous_hsm_id: str | None = None,
    data: WhatsAppCloudApiTemplateCreate,
) -> WhatsAppCloudApiTemplateResponse:
    """Replace a live Meta template with an edited copy.

    Meta's template contract is immutable, so an edit cannot update the
    existing template in place. Editing deletes the current template and
    submits the edited payload as a new one for review. The previous name is
    required to remove the old catalog entry; ``previous_hsm_id`` restricts
    the delete to the single language variant being edited.
    """

    integration = _cloud_template_integration(
        session=session, integration_id=integration_id, current_user=current_user
    )
    try:
        deleted = MetaCloudApiClient(
            _cloud_credentials(integration)
        ).delete_message_template(name=previous_name, hsm_id=previous_hsm_id)
        if not deleted:
            raise HTTPException(
                status_code=502,
                detail="Meta did not confirm the previous template deletion",
            )
        payload = data.model_dump()
        payload["language"] = payload["language"].replace("-", "_")
        payload["category"] = payload["category"].upper()
        response = MetaCloudApiClient(
            _cloud_credentials(integration)
        ).create_message_template(payload)
    except MetaCloudApiError as exc:
        raise _cloud_error(exc) from exc
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="template.updated",
        instance_id=integration.id,
    )
    return WhatsAppCloudApiTemplateResponse(
        id=str(response.get("id") or ""),
        name=data.name,
        language=payload["language"],
        status=str(response.get("status") or "PENDING"),
        category=str(response.get("category") or payload["category"]),
        components=data.components,
        quality_score=None,
        rejected_reason=None,
    )


def get_integration(
    *, session: Session, integration_id: uuid.UUID, current_user: User
) -> WhatsAppIntegration:
    return _get_integration(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
    )


def update_integration(
    *,
    session: Session,
    integration_id: uuid.UUID,
    current_user: User,
    data: WhatsAppIntegrationUpdate,
) -> WhatsAppIntegration:
    integration = _get_integration(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
    )
    values = data.model_dump(exclude_unset=True)
    protected_cloud_fields = {
        "adapter",
        "integration_type",
        "phone_number",
        "external_account_id",
        "credentials",
        "config",
    }
    if integration.adapter == META_CLOUD_API_ADAPTER and (
        protected_cloud_fields.intersection(values)
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Use PUT /whatsapp/instances/{id}/cloud-api to change "
                "Meta Cloud API credentials or provider configuration"
            ),
        )
    if values.get("adapter") == META_CLOUD_API_ADAPTER:
        raise HTTPException(
            status_code=422,
            detail=(
                "Use POST /whatsapp/instances/cloud-api to create a "
                "verified Meta Cloud API connection"
            ),
        )
    for field in ("name", "adapter", "phone_number", "external_account_id"):
        if field in values:
            setattr(integration, field, values[field])
    if "integration_type" in values and values["integration_type"] is not None:
        integration.integration_type = values["integration_type"].value
    if "credentials" in values:
        integration.credentials_json = values["credentials"] or {}
    if "config" in values:
        integration.config_json = values["config"] or {}
    if "is_active" in values and values["is_active"] is not None:
        integration.is_active = values["is_active"]
    integration.updated_at = _now()
    session.add(integration)
    _commit(session)
    session.refresh(integration)
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="instance.updated",
        instance_id=integration.id,
    )
    return integration


def delete_integration(
    *, session: Session, integration_id: uuid.UUID, current_user: User
) -> None:
    integration = _get_integration(
        session=session,
        integration_id=integration_id,
        current_user=current_user,
    )
    integration.is_active = False
    integration.updated_at = _now()
    session.add(integration)
    _commit(session)
    whatsapp_event_broker.publish(
        company_id=integration.company_id,
        event_type="instance.deleted",
        instance_id=integration.id,
    )


def list_contacts(
    *,
    session: Session,
    current_user: User,
    integration_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WhatsAppContact]:
    if integration_id is not None:
        integration = _get_integration(
            session=session,
            integration_id=integration_id,
            current_user=current_user,
        )
        integration_ids = [integration.id]
    else:
        company_ids = _accessible_company_ids(
            session=session,
            current_user=current_user,
            company_id=company_id,
        )
        active_integrations = select(WhatsAppIntegration.id).where(
            WhatsAppIntegration.company_id.in_(company_ids),
            WhatsAppIntegration.is_active == True,
        )
        statement = (
            select(WhatsAppContact)
            .where(
                WhatsAppContact.integration_id.in_(active_integrations),
                WhatsAppContact.is_active == True,
            )
            .order_by(desc(WhatsAppContact.created_at))
            .offset(offset)
            .limit(limit)
        )
        return list(session.exec(statement).all())

    statement = (
        select(WhatsAppContact)
        .where(
            WhatsAppContact.integration_id.in_(integration_ids),
            WhatsAppContact.is_active == True,
        )
        .order_by(desc(WhatsAppContact.created_at))
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def create_contact(
    *,
    session: Session,
    current_user: User,
    data: WhatsAppContactCreate,
) -> WhatsAppContact:
    integration = _get_integration(
        session=session,
        integration_id=data.instance_id,
        current_user=current_user,
    )
    phone_number = data.phone_number
    if integration.adapter == META_CLOUD_API_ADAPTER:
        try:
            phone_number = format_phone_number_for_meta(phone_number)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    contact = WhatsAppContact(
        company_id=integration.company_id,
        integration_id=integration.id,
        external_id=data.external_id,
        phone_number=phone_number,
        name=data.name,
        profile_picture_url=data.profile_picture_url,
        is_blocked=data.is_blocked,
        metadata_json=data.metadata,
    )
    session.add(contact)
    _commit(session)
    session.refresh(contact)
    whatsapp_event_broker.publish(
        company_id=contact.company_id,
        event_type="contact.created",
        instance_id=contact.integration_id,
    )
    return contact


def get_contact(
    *, session: Session, contact_id: uuid.UUID, current_user: User
) -> WhatsAppContact:
    return _get_contact(
        session=session,
        contact_id=contact_id,
        current_user=current_user,
    )


def update_contact(
    *,
    session: Session,
    contact_id: uuid.UUID,
    current_user: User,
    data: WhatsAppContactUpdate,
) -> WhatsAppContact:
    contact = _get_contact(
        session=session,
        contact_id=contact_id,
        current_user=current_user,
    )
    values = data.model_dump(exclude_unset=True)
    for field in ("external_id", "name", "profile_picture_url"):
        if field in values:
            setattr(contact, field, values[field])
    if "phone_number" in values and values["phone_number"] is not None:
        phone_number = values["phone_number"]
        integration = _get_integration(
            session=session,
            integration_id=contact.integration_id,
            current_user=current_user,
        )
        if integration.adapter == META_CLOUD_API_ADAPTER:
            try:
                phone_number = format_phone_number_for_meta(phone_number)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        contact.phone_number = phone_number
    for field in ("is_blocked", "is_active"):
        if field in values and values[field] is not None:
            setattr(contact, field, values[field])
    if "metadata" in values:
        contact.metadata_json = values["metadata"] or {}
    contact.updated_at = _now()
    session.add(contact)
    _commit(session)
    session.refresh(contact)
    whatsapp_event_broker.publish(
        company_id=contact.company_id,
        event_type="contact.updated",
        instance_id=contact.integration_id,
    )
    return contact


def delete_contact(
    *, session: Session, contact_id: uuid.UUID, current_user: User
) -> None:
    contact = _get_contact(
        session=session,
        contact_id=contact_id,
        current_user=current_user,
    )
    contact.is_active = False
    contact.updated_at = _now()
    session.add(contact)
    _commit(session)
    whatsapp_event_broker.publish(
        company_id=contact.company_id,
        event_type="contact.deleted",
        instance_id=contact.integration_id,
    )


def list_conversations(
    *,
    session: Session,
    current_user: User,
    integration_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WhatsAppConversation]:
    if integration_id is not None:
        integration = _get_integration(
            session=session,
            integration_id=integration_id,
            current_user=current_user,
        )
        integration_ids = [integration.id]
    else:
        company_ids = _accessible_company_ids(
            session=session,
            current_user=current_user,
            company_id=company_id,
        )
        active_integrations = select(WhatsAppIntegration.id).where(
            WhatsAppIntegration.company_id.in_(company_ids),
            WhatsAppIntegration.is_active == True,
        )
        integration_ids = active_integrations

    conditions = [
        WhatsAppConversation.integration_id.in_(integration_ids),
        WhatsAppConversation.is_active == True,
    ]
    if contact_id is not None:
        contact = _get_contact(
            session=session,
            contact_id=contact_id,
            current_user=current_user,
        )
        conditions.append(WhatsAppConversation.contact_id == contact.id)
    statement = (
        select(WhatsAppConversation)
        .where(*conditions)
        .order_by(desc(WhatsAppConversation.last_message_at))
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def create_conversation(
    *,
    session: Session,
    current_user: User,
    data: WhatsAppConversationCreate,
) -> WhatsAppConversation:
    integration = _get_integration(
        session=session,
        integration_id=data.instance_id,
        current_user=current_user,
    )
    if data.contact_id is not None:
        contact = _get_contact(
            session=session,
            contact_id=data.contact_id,
            current_user=current_user,
        )
        if contact.integration_id != integration.id:
            raise HTTPException(
                status_code=422,
                detail="Contact does not belong to the selected integration",
            )
    conversation = WhatsAppConversation(
        company_id=integration.company_id,
        integration_id=integration.id,
        contact_id=data.contact_id,
        external_id=data.external_id,
        title=data.title,
        status=data.status.value,
        metadata_json=data.metadata,
    )
    session.add(conversation)
    _commit(session)
    session.refresh(conversation)
    whatsapp_event_broker.publish(
        company_id=conversation.company_id,
        event_type="conversation.created",
        instance_id=conversation.integration_id,
        conversation_id=conversation.id,
    )
    return conversation


def get_conversation(
    *, session: Session, conversation_id: uuid.UUID, current_user: User
) -> WhatsAppConversation:
    return _get_conversation(
        session=session,
        conversation_id=conversation_id,
        current_user=current_user,
    )


def update_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    current_user: User,
    data: WhatsAppConversationUpdate,
) -> WhatsAppConversation:
    conversation = _get_conversation(
        session=session,
        conversation_id=conversation_id,
        current_user=current_user,
    )
    values = data.model_dump(exclude_unset=True)
    if "contact_id" in values and values["contact_id"] is not None:
        contact = _get_contact(
            session=session,
            contact_id=values["contact_id"],
            current_user=current_user,
        )
        if contact.integration_id != conversation.integration_id:
            raise HTTPException(
                status_code=422,
                detail="Contact does not belong to the conversation integration",
            )
    for field in ("contact_id", "external_id", "title", "is_active"):
        if field in values:
            setattr(conversation, field, values[field])
    if "status" in values and values["status"] is not None:
        conversation.status = values["status"].value
    if "metadata" in values:
        conversation.metadata_json = values["metadata"] or {}
    conversation.updated_at = _now()
    session.add(conversation)
    _commit(session)
    session.refresh(conversation)
    whatsapp_event_broker.publish(
        company_id=conversation.company_id,
        event_type="conversation.updated",
        instance_id=conversation.integration_id,
        conversation_id=conversation.id,
    )
    return conversation


def delete_conversation(
    *, session: Session, conversation_id: uuid.UUID, current_user: User
) -> None:
    conversation = _get_conversation(
        session=session,
        conversation_id=conversation_id,
        current_user=current_user,
    )
    conversation.is_active = False
    conversation.updated_at = _now()
    session.add(conversation)
    _commit(session)
    whatsapp_event_broker.publish(
        company_id=conversation.company_id,
        event_type="conversation.deleted",
        instance_id=conversation.integration_id,
        conversation_id=conversation.id,
    )


def list_messages(
    *,
    session: Session,
    current_user: User,
    conversation_id: uuid.UUID | None = None,
    integration_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[WhatsAppMessage]:
    if conversation_id is not None:
        conversation = _get_conversation(
            session=session,
            conversation_id=conversation_id,
            current_user=current_user,
        )
        conditions = [WhatsAppMessage.conversation_id == conversation.id]
    elif integration_id is not None:
        integration = _get_integration(
            session=session,
            integration_id=integration_id,
            current_user=current_user,
        )
        conditions = [WhatsAppMessage.integration_id == integration.id]
    else:
        company_ids = _accessible_company_ids(
            session=session,
            current_user=current_user,
            company_id=company_id,
        )
        active_integrations = select(WhatsAppIntegration.id).where(
            WhatsAppIntegration.company_id.in_(company_ids),
            WhatsAppIntegration.is_active == True,
        )
        conditions = [WhatsAppMessage.integration_id.in_(active_integrations)]
    conditions.append(WhatsAppMessage.is_active == True)
    statement = (
        select(WhatsAppMessage)
        .where(*conditions)
        .order_by(asc(WhatsAppMessage.created_at))
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def create_message(
    *,
    session: Session,
    current_user: User,
    data: WhatsAppMessageCreate,
) -> WhatsAppMessage:
    conversation = _get_conversation(
        session=session,
        conversation_id=data.conversation_id,
        current_user=current_user,
    )
    integration = _get_integration(
        session=session,
        integration_id=conversation.integration_id,
        current_user=current_user,
    )
    created_at = _now()
    metadata = dict(data.metadata)
    external_id = data.external_id
    status = data.status.value
    sent_at = data.sent_at

    is_internal = data.message_type in INTERNAL_MESSAGE_TYPES or bool(
        metadata.get("internal")
    )
    if (
        data.direction == MessageDirection.OUTBOUND
        and (integration.adapter == META_CLOUD_API_ADAPTER)
        and not is_internal
    ):
        if conversation.contact_id is None:
            raise HTTPException(
                status_code=422,
                detail="An outbound Meta Cloud API message requires a conversation contact",
            )
        contact = _get_contact(
            session=session,
            contact_id=conversation.contact_id,
            current_user=current_user,
        )
        metadata["recipient_phone_number"] = contact.phone_number
        pending_message = WhatsAppMessage(
            company_id=conversation.company_id,
            integration_id=conversation.integration_id,
            conversation_id=conversation.id,
            external_id=external_id,
            direction=data.direction.value,
            message_type=data.message_type,
            content=data.content,
            media_url=data.media_url,
            status=MessageStatus.PENDING.value,
            metadata_json=metadata,
            created_at=created_at,
            updated_at=created_at,
        )
        try:
            adapter = whatsapp_adapter_registry.resolve(integration)
            result = adapter.send_message(
                integration=integration,
                message=pending_message,
            )
        except MetaCloudApiError as exc:
            raise _cloud_error(exc) from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail="The WhatsApp adapter could not send the message",
            ) from exc
        external_id = result.external_id
        status = (
            result.status
            if result.status
            in {
                MessageStatus.SENT.value,
                MessageStatus.DELIVERED.value,
                MessageStatus.READ.value,
                MessageStatus.FAILED.value,
            }
            else MessageStatus.SENT.value
        )
        sent_at = created_at
        if result.raw:
            metadata["provider_response"] = result.raw

    message = WhatsAppMessage(
        company_id=conversation.company_id,
        integration_id=conversation.integration_id,
        conversation_id=conversation.id,
        external_id=external_id,
        direction=data.direction.value,
        message_type=data.message_type,
        content=data.content,
        media_url=data.media_url,
        status=status,
        metadata_json=metadata,
        sent_at=sent_at,
        created_at=created_at,
        updated_at=created_at,
    )
    conversation.last_message_at = created_at
    conversation.updated_at = created_at
    session.add(message)
    session.add(conversation)
    _commit(session)
    session.refresh(message)
    whatsapp_event_broker.publish(
        company_id=message.company_id,
        event_type="message.created",
        instance_id=message.integration_id,
        conversation_id=message.conversation_id,
        message_id=message.id,
    )
    return message


def get_message(
    *, session: Session, message_id: uuid.UUID, current_user: User
) -> WhatsAppMessage:
    return _get_message(
        session=session,
        message_id=message_id,
        current_user=current_user,
    )


def update_message(
    *,
    session: Session,
    message_id: uuid.UUID,
    current_user: User,
    data: WhatsAppMessageUpdate,
) -> WhatsAppMessage:
    message = _get_message(
        session=session,
        message_id=message_id,
        current_user=current_user,
    )
    values = data.model_dump(exclude_unset=True)
    if "direction" in values and values["direction"] is not None:
        message.direction = values["direction"].value
    if "status" in values and values["status"] is not None:
        message.status = values["status"].value
    for field in ("external_id", "message_type", "content", "media_url", "sent_at"):
        if field in values:
            setattr(message, field, values[field])
    if "metadata" in values:
        message.metadata_json = values["metadata"] or {}
    message.updated_at = _now()
    session.add(message)
    _commit(session)
    session.refresh(message)
    whatsapp_event_broker.publish(
        company_id=message.company_id,
        event_type="message.updated",
        instance_id=message.integration_id,
        conversation_id=message.conversation_id,
        message_id=message.id,
    )
    return message


def delete_message(
    *, session: Session, message_id: uuid.UUID, current_user: User
) -> None:
    message = _get_message(
        session=session,
        message_id=message_id,
        current_user=current_user,
    )
    message.is_active = False
    message.updated_at = _now()
    session.add(message)
    _commit(session)
    whatsapp_event_broker.publish(
        company_id=message.company_id,
        event_type="message.deleted",
        instance_id=message.integration_id,
        conversation_id=message.conversation_id,
        message_id=message.id,
    )


def _internal_message(
    *,
    conversation: WhatsAppConversation,
    message_type: str,
    role: str,
    content: str,
    created_at: datetime.datetime | None = None,
) -> WhatsAppMessage:
    timestamp = created_at or _now()
    return WhatsAppMessage(
        company_id=conversation.company_id,
        integration_id=conversation.integration_id,
        conversation_id=conversation.id,
        direction=MessageDirection.INBOUND.value,
        message_type=message_type,
        content=content,
        status=MessageStatus.SENT.value,
        metadata_json={"internal": True, "kind": message_type, "role": role},
        sent_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )


def create_note(
    *,
    session: Session,
    current_user: User,
    conversation_id: uuid.UUID,
    content: str,
) -> WhatsAppMessage:
    conversation = _get_conversation(
        session=session,
        conversation_id=conversation_id,
        current_user=current_user,
    )
    created_at = _now()
    note = _internal_message(
        conversation=conversation,
        message_type="note",
        role="operator",
        content=content,
        created_at=created_at,
    )
    conversation.last_message_at = created_at
    conversation.updated_at = created_at
    session.add(note)
    session.add(conversation)
    _commit(session)
    session.refresh(note)
    whatsapp_event_broker.publish(
        company_id=note.company_id,
        event_type="message.created",
        instance_id=note.integration_id,
        conversation_id=note.conversation_id,
        message_id=note.id,
    )
    return note


def create_ai_message(
    *,
    session: Session,
    current_user: User,
    conversation_id: uuid.UUID,
    prompt: str,
    auth_token: str | None = None,
) -> tuple[WhatsAppMessage, WhatsAppMessage, str]:
    conversation = _get_conversation(
        session=session,
        conversation_id=conversation_id,
        current_user=current_user,
    )

    recent_messages = (
        select(WhatsAppMessage)
        .where(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.is_active == True,
            ~WhatsAppMessage.message_type.in_(INTERNAL_MESSAGE_TYPES),
            WhatsAppMessage.content.is_not(None),
        )
        .order_by(desc(WhatsAppMessage.created_at))
        .limit(30)
    )
    history = list(reversed(session.exec(recent_messages).all()))
    context = [
        {
            "role": "user"
            if message.direction == MessageDirection.INBOUND.value
            else "assistant",
            "content": message.content or "",
        }
        for message in history
    ]

    created_at = _now()
    prompt_message = _internal_message(
        conversation=conversation,
        message_type="ai",
        role="user",
        content=prompt,
        created_at=created_at,
    )

    # Imported lazily to keep the WhatsApp module decoupled from the AI stack.
    from app.modules.ai.service import llm

    system_prompt = (
        "You are an AI assistant embedded in a customer-support WhatsApp inbox. "
        "You help the operator draft replies to the contact. Use the conversation "
        "history as context and answer in the same language as the customer. "
        "Reply directly with a ready-to-send draft, concise and friendly. "
        "Do NOT call any tools and never send or create messages."
    )
    try:
        result = llm.generate(
            prompt=prompt,
            context=context,
            system_prompt=system_prompt,
            auth_token=auth_token,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI assistant failed: {exc}",
        ) from exc

    response_text = result.response.strip()
    if not response_text:
        raise HTTPException(
            status_code=502,
            detail="The AI assistant returned an empty reply",
        )

    assistant_message = _internal_message(
        conversation=conversation,
        message_type="ai",
        role="assistant",
        content=response_text,
        created_at=created_at,
    )

    conversation.last_message_at = created_at
    conversation.updated_at = created_at
    session.add(prompt_message)
    session.add(assistant_message)
    session.add(conversation)
    _commit(session)
    session.refresh(prompt_message)
    session.refresh(assistant_message)
    for message in (prompt_message, assistant_message):
        whatsapp_event_broker.publish(
            company_id=message.company_id,
            event_type="message.created",
            instance_id=message.integration_id,
            conversation_id=message.conversation_id,
            message_id=message.id,
        )
    return prompt_message, assistant_message, response_text


def create_internal_ai_draft(
    *,
    session: Session,
    conversation: WhatsAppConversation,
    content: str,
    metadata: dict[str, Any] | None = None,
    created_at: datetime.datetime | None = None,
) -> WhatsAppMessage:
    """Store the AI's auto-reply as an internal draft in the timeline.

    Internal AI messages are never delivered to the contact; the corresponding
    outbound message is created separately by ``create_ai_reply_message``.
    """
    timestamp = created_at or _now()
    draft = _internal_message(
        conversation=conversation,
        message_type="ai",
        role="assistant",
        content=content,
        created_at=timestamp,
    )
    draft.metadata_json = {**draft.metadata_json, **(metadata or {})}
    conversation.last_message_at = timestamp
    conversation.updated_at = timestamp
    session.add(draft)
    session.add(conversation)
    _commit(session)
    session.refresh(draft)
    whatsapp_event_broker.publish(
        company_id=draft.company_id,
        event_type="message.created",
        instance_id=draft.integration_id,
        conversation_id=draft.conversation_id,
        message_id=draft.id,
    )
    return draft


def create_ai_failure_note(
    *,
    session: Session,
    conversation: WhatsAppConversation,
    reason: str,
    reply_to_message: WhatsAppMessage | None = None,
    created_at: datetime.datetime | None = None,
) -> WhatsAppMessage:
    """Store an internal note when the AI could not answer an inbound message."""
    timestamp = created_at or _now()
    content = f"AI auto-reply failed: {reason}"
    metadata = {"ai_kind": "auto_reply_failure"}
    if reply_to_message is not None:
        metadata["reply_to_message_id"] = str(reply_to_message.id)
    note = _internal_message(
        conversation=conversation,
        message_type="note",
        role="system",
        content=content,
        created_at=timestamp,
    )
    note.metadata_json = {**note.metadata_json, **metadata}
    session.add(note)
    _commit(session)
    session.refresh(note)
    whatsapp_event_broker.publish(
        company_id=note.company_id,
        event_type="message.created",
        instance_id=note.integration_id,
        conversation_id=note.conversation_id,
        message_id=note.id,
    )
    return note


def create_ai_reply_message(
    *,
    session: Session,
    conversation: WhatsAppConversation,
    content: str,
    reply_to_message: WhatsAppMessage | None = None,
) -> WhatsAppMessage:
    """Deliver the AI's reply to the contact through the integration adapter.

    Reuses the same delivery path as ``create_message`` for outbound messages,
    without requiring an authenticated user because replies are generated in a
    background worker on behalf of the company.
    """
    integration = session.get(WhatsAppIntegration, conversation.integration_id)
    if integration is None or not integration.is_active:
        raise HTTPException(
            status_code=404, detail="WhatsApp integration not found"
        )
    created_at = _now()
    metadata: dict[str, Any] = {"ai_kind": "auto_reply"}
    if reply_to_message is not None:
        metadata["reply_to_message_id"] = str(reply_to_message.id)

    external_id: str | None = None
    status = MessageStatus.SENT.value
    sent_at: datetime.datetime | None = None

    if integration.adapter == META_CLOUD_API_ADAPTER:
        if conversation.contact_id is None:
            raise HTTPException(
                status_code=422,
                detail="An outbound Meta Cloud API message requires a conversation contact",
            )
        contact = session.get(WhatsAppContact, conversation.contact_id)
        if contact is None:
            raise HTTPException(status_code=404, detail="WhatsApp contact not found")
        metadata["recipient_phone_number"] = contact.phone_number
        pending_message = WhatsAppMessage(
            company_id=conversation.company_id,
            integration_id=conversation.integration_id,
            conversation_id=conversation.id,
            direction=MessageDirection.OUTBOUND.value,
            message_type="text",
            content=content,
            status=MessageStatus.PENDING.value,
            metadata_json=metadata,
            created_at=created_at,
            updated_at=created_at,
        )
        try:
            adapter = whatsapp_adapter_registry.resolve(integration)
            result = adapter.send_message(
                integration=integration,
                message=pending_message,
            )
        except MetaCloudApiError as exc:
            raise _cloud_error(exc) from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail="The WhatsApp adapter could not send the message",
            ) from exc
        external_id = result.external_id
        status = (
            result.status
            if result.status
            in {
                MessageStatus.SENT.value,
                MessageStatus.DELIVERED.value,
                MessageStatus.READ.value,
                MessageStatus.FAILED.value,
            }
            else MessageStatus.SENT.value
        )
        sent_at = created_at
        if result.raw:
            metadata["provider_response"] = result.raw

    message = WhatsAppMessage(
        company_id=conversation.company_id,
        integration_id=conversation.integration_id,
        conversation_id=conversation.id,
        external_id=external_id,
        direction=MessageDirection.OUTBOUND.value,
        message_type="text",
        content=content,
        status=status,
        metadata_json=metadata,
        sent_at=sent_at,
        created_at=created_at,
        updated_at=created_at,
    )
    conversation.last_message_at = created_at
    conversation.updated_at = created_at
    session.add(message)
    session.add(conversation)
    _commit(session)
    session.refresh(message)
    whatsapp_event_broker.publish(
        company_id=message.company_id,
        event_type="message.created",
        instance_id=message.integration_id,
        conversation_id=message.conversation_id,
        message_id=message.id,
    )
    return message


def verify_meta_webhook(
    *,
    session: Session,
    mode: str | None,
    verify_token: str | None,
    challenge: str | None,
) -> str:
    """Handle Meta's GET challenge for the shared public webhook endpoint."""

    if mode != "subscribe" or not verify_token or challenge is None:
        raise HTTPException(status_code=403, detail="Invalid Meta webhook verification")

    statement = select(WhatsAppIntegration).where(
        WhatsAppIntegration.adapter == META_CLOUD_API_ADAPTER,
        WhatsAppIntegration.is_active == True,
    )
    for integration in session.exec(statement).all():
        configured_token = integration.credentials_json.get("webhook_verify_token")
        if isinstance(configured_token, str) and hmac.compare_digest(
            configured_token, verify_token
        ):
            return challenge
    raise HTTPException(status_code=403, detail="Invalid Meta webhook verification")


def _cloud_integrations_for_webhook(
    *, session: Session, waba_ids: set[str]
) -> list[WhatsAppIntegration]:
    if not waba_ids:
        return []
    statement = select(WhatsAppIntegration).where(
        WhatsAppIntegration.adapter == META_CLOUD_API_ADAPTER,
        cast(Any, WhatsAppIntegration.external_account_id).in_(waba_ids),
        WhatsAppIntegration.is_active == True,
    )
    return list(session.exec(statement).all())


def _webhook_timestamp(value: object) -> datetime.datetime:
    try:
        return datetime.datetime.fromtimestamp(int(str(value)), datetime.UTC).replace(
            tzinfo=None
        )
    except (TypeError, ValueError, OverflowError):
        return _now()


def _upsert_webhook_contact(
    *,
    session: Session,
    integration: WhatsAppIntegration,
    phone_number: str,
    contact_payload: dict[str, object] | None,
) -> WhatsAppContact:
    statement = select(WhatsAppContact).where(
        WhatsAppContact.integration_id == integration.id,
        WhatsAppContact.external_id == phone_number,
    )
    contact = session.exec(statement).first()
    profile = contact_payload or {}
    profile_data = profile.get("profile")
    if isinstance(profile_data, dict):
        name = profile_data.get("name")
    else:
        name = profile.get("name")
    metadata = {
        "provider": "meta",
        "wa_id": phone_number,
        "profile": profile,
    }
    if contact is None:
        contact = WhatsAppContact(
            company_id=integration.company_id,
            integration_id=integration.id,
            external_id=phone_number,
            phone_number=phone_number,
            name=name if isinstance(name, str) else None,
            metadata_json=metadata,
        )
    else:
        contact.phone_number = phone_number
        if isinstance(name, str) and name:
            contact.name = name
        contact.metadata_json = {**contact.metadata_json, **metadata}
        contact.is_active = True
        contact.updated_at = _now()
    session.add(contact)
    session.flush()
    return contact


def _message_content(message_payload: dict[str, object]) -> str | None:
    message_type = message_payload.get("type")
    if message_type == "text":
        text = message_payload.get("text")
        if isinstance(text, dict) and isinstance(text.get("body"), str):
            return text["body"]
    if message_type in {"image", "audio", "video", "document", "sticker"}:
        media = message_payload.get(str(message_type))
        if isinstance(media, dict):
            caption = media.get("caption")
            if isinstance(caption, str):
                return caption
    button = message_payload.get("button")
    if isinstance(button, dict):
        title = button.get("text")
        if isinstance(title, str):
            return title
    interactive = message_payload.get("interactive")
    if isinstance(interactive, dict):
        button_reply = interactive.get("button_reply")
        if isinstance(button_reply, dict) and isinstance(
            button_reply.get("title"), str
        ):
            return button_reply["title"]
        list_reply = interactive.get("list_reply")
        if isinstance(list_reply, dict) and isinstance(list_reply.get("title"), str):
            return list_reply["title"]
    reaction = message_payload.get("reaction")
    if isinstance(reaction, dict) and isinstance(reaction.get("emoji"), str):
        return reaction["emoji"]
    location = message_payload.get("location")
    if isinstance(location, dict):
        name = location.get("name") or location.get("address")
        if isinstance(name, str):
            return name
    contacts = message_payload.get("contacts")
    if isinstance(contacts, list):
        names: list[str] = []
        for contact in contacts:
            if not isinstance(contact, dict):
                continue
            contact_name = contact.get("name")
            if isinstance(contact_name, dict) and isinstance(
                contact_name.get("formatted_name"), str
            ):
                names.append(contact_name["formatted_name"])
        if names:
            return ", ".join(names)
    return None


def _message_media_reference(message_payload: dict[str, object]) -> str | None:
    message_type = message_payload.get("type")
    if not isinstance(message_type, str):
        return None
    media = message_payload.get(message_type)
    if not isinstance(media, dict):
        return None
    for key in ("id", "link"):
        reference = media.get(key)
        if isinstance(reference, str) and reference:
            return reference
    return None


_MEDIA_MESSAGE_TYPES = {"image", "audio", "video", "document", "sticker"}


def _store_inbound_media(
    *,
    integration: WhatsAppIntegration,
    message_payload: dict[str, object],
    external_id: str,
) -> tuple[str, dict[str, object]]:
    """Download an inbound Meta media file and persist it to R2.

    Returns the stored ``media_url`` and any metadata to merge. When R2 or the
    download fails, the raw Meta media id is kept as ``media_url`` so the
    message is still stored and can be retried later.
    """
    reference = _message_media_reference(message_payload)
    if not reference:
        return "", {}
    if reference.startswith(("http://", "https://")):
        return reference, {}

    if not r2.configured:
        return reference, {"media_r2_status": "storage_not_configured"}

    try:
        credentials = _cloud_credentials(integration)
        client = MetaCloudApiClient(credentials)
        media: MediaDownload = client.retrieve_media(reference)
    except (MetaCloudApiError, HTTPException) as exc:
        return reference, {"media_r2_status": "download_failed", "media_error": str(exc)}

    extension = _extension_for(media.mime_type)
    base_name = _safe_filename(media.filename) if media.filename else external_id
    stem = Path(base_name).stem or "media"
    key = f"whatsapp/{integration.company_id}/{integration.id}/media/{external_id}/{stem}{extension}"
    try:
        stored = r2.put_object(
            key=key,
            data=media.data,
            content_type=media.mime_type or "application/octet-stream",
        )
    except R2Error as exc:
        return reference, {"media_r2_status": "upload_failed", "media_error": str(exc)}
    return stored.url, {
        "media_r2_status": "stored",
        "media_r2_key": stored.key,
        "media_size_bytes": stored.size_bytes,
        "media_mime_type": media.mime_type,
    }


def _process_webhook_change(
    *,
    session: Session,
    integration: WhatsAppIntegration,
    value: dict[str, object],
    inbound_message_ids: list[uuid.UUID] | None = None,
) -> int:
    configured_phone_number_id = integration.config_json.get("phone_number_id")
    metadata = value.get("metadata")
    if isinstance(metadata, dict):
        incoming_phone_number_id = metadata.get("phone_number_id")
        if (
            configured_phone_number_id
            and incoming_phone_number_id
            and str(incoming_phone_number_id) != str(configured_phone_number_id)
        ):
            return 0

    contacts_by_id: dict[str, dict[str, object]] = {}
    contacts = value.get("contacts")
    if isinstance(contacts, list):
        for item in contacts:
            if isinstance(item, dict) and item.get("wa_id"):
                contacts_by_id[str(item["wa_id"])] = item

    processed = 0
    messages = value.get("messages")
    if isinstance(messages, list):
        for message_payload in messages:
            if not isinstance(message_payload, dict):
                continue
            external_id = message_payload.get("id")
            phone_number = message_payload.get("from")
            if not external_id or not phone_number:
                continue
            external_id = str(external_id)
            phone_number = str(phone_number)
            contact = _upsert_webhook_contact(
                session=session,
                integration=integration,
                phone_number=phone_number,
                contact_payload=contacts_by_id.get(phone_number),
            )
            conversation_statement = select(WhatsAppConversation).where(
                WhatsAppConversation.integration_id == integration.id,
                WhatsAppConversation.external_id == phone_number,
            )
            conversation = session.exec(conversation_statement).first()
            now = _webhook_timestamp(message_payload.get("timestamp"))
            if conversation is None:
                conversation = WhatsAppConversation(
                    company_id=integration.company_id,
                    integration_id=integration.id,
                    contact_id=contact.id,
                    external_id=phone_number,
                    title=contact.name,
                    last_message_at=now,
                )
            else:
                conversation.contact_id = contact.id
                conversation.last_message_at = max(
                    conversation.last_message_at or now, now
                )
                conversation.updated_at = _now()
                conversation.is_active = True
            session.add(conversation)
            session.flush()

            existing_statement = select(WhatsAppMessage).where(
                WhatsAppMessage.integration_id == integration.id,
                WhatsAppMessage.external_id == external_id,
            )
            existing_message = session.exec(existing_statement).first()
            message_type = str(message_payload.get("type") or "text")[:32]
            message_metadata = {
                "provider": "meta",
                "phone_number_id": configured_phone_number_id,
                "raw": message_payload,
            }

            media_url = _message_media_reference(message_payload)
            if message_type in _MEDIA_MESSAGE_TYPES and media_url:
                stored_url, media_metadata = _store_inbound_media(
                    integration=integration,
                    message_payload=message_payload,
                    external_id=external_id,
                )
                media_url = stored_url or media_url
                message_metadata.update(media_metadata)

            was_new = existing_message is None
            if existing_message is None:
                existing_message = WhatsAppMessage(
                    company_id=integration.company_id,
                    integration_id=integration.id,
                    conversation_id=conversation.id,
                    external_id=external_id,
                    direction=MessageDirection.INBOUND.value,
                    message_type=message_type,
                    content=_message_content(message_payload),
                    media_url=media_url,
                    status=MessageStatus.SENT.value,
                    metadata_json=message_metadata,
                    sent_at=now,
                    created_at=now,
                    updated_at=now,
                )
            else:
                existing_message.conversation_id = conversation.id
                existing_message.metadata_json = {
                    **existing_message.metadata_json,
                    **message_metadata,
                }
                if media_url:
                    existing_message.media_url = media_url
                existing_message.is_active = True
                existing_message.updated_at = _now()
            session.add(existing_message)
            processed += 1
            if inbound_message_ids is not None and was_new:
                inbound_message_ids.append(existing_message.id)

    statuses = value.get("statuses")
    if isinstance(statuses, list):
        for status_payload in statuses:
            if not isinstance(status_payload, dict) or not status_payload.get("id"):
                continue
            statement = select(WhatsAppMessage).where(
                WhatsAppMessage.integration_id == integration.id,
                WhatsAppMessage.external_id == str(status_payload["id"]),
            )
            message = session.exec(statement).first()
            if message is None:
                continue
            status_value = str(status_payload.get("status") or "pending")
            if status_value not in {
                MessageStatus.SENT.value,
                MessageStatus.DELIVERED.value,
                MessageStatus.READ.value,
                MessageStatus.FAILED.value,
            }:
                status_value = MessageStatus.PENDING.value
            message.status = status_value
            if (
                status_value
                in {
                    MessageStatus.SENT.value,
                    MessageStatus.DELIVERED.value,
                    MessageStatus.READ.value,
                }
                and message.sent_at is None
            ):
                message.sent_at = _webhook_timestamp(status_payload.get("timestamp"))
            message.metadata_json = {
                **message.metadata_json,
                "last_status": status_payload,
            }
            message.updated_at = _now()
            session.add(message)
            processed += 1
    return processed


def process_meta_webhook(
    *,
    session: Session,
    raw_payload: bytes,
    signature_header: str | None,
) -> dict[str, int | bool]:
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400, detail="Invalid Meta webhook JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Meta webhook payload")

    entries = payload.get("entry")
    if not isinstance(entries, list):
        return {"received": True, "processed": 0}
    waba_ids = {
        str(entry["id"])
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    }
    integrations = _cloud_integrations_for_webhook(
        session=session,
        waba_ids=waba_ids,
    )
    if not integrations:
        return {"received": True, "processed": 0}

    valid_integrations = []
    for integration in integrations:
        try:
            credentials = _cloud_credentials(integration)
        except HTTPException:
            continue
        if verify_webhook_signature(
            raw_payload,
            signature_header,
            credentials.app_secret,
        ):
            valid_integrations.append(integration)
    if not valid_integrations:
        raise HTTPException(status_code=403, detail="Invalid Meta webhook signature")

    processed = 0
    template_catalog_changed = False
    inbound_message_ids: list[uuid.UUID] = []
    for integration in valid_integrations:
        for entry in entries:
            if not isinstance(entry, dict) or str(entry.get("id")) != str(
                integration.external_account_id
            ):
                continue
            changes = entry.get("changes")
            if not isinstance(changes, list):
                continue
            for change in changes:
                if not isinstance(change, dict):
                    continue
                field = str(change.get("field") or "").lower()
                template_catalog_changed = (
                    template_catalog_changed or "template" in field
                )
                value = change.get("value")
                if isinstance(value, dict):
                    processed += _process_webhook_change(
                        session=session,
                        integration=integration,
                        value=value,
                        inbound_message_ids=inbound_message_ids,
                    )
    if processed or template_catalog_changed:
        _commit(session)
        for integration in valid_integrations:
            whatsapp_event_broker.publish(
                company_id=integration.company_id,
                event_type="inbox.changed",
                instance_id=integration.id,
            )
            if template_catalog_changed:
                whatsapp_event_broker.publish(
                    company_id=integration.company_id,
                    event_type="template.updated",
                    instance_id=integration.id,
                )
    if inbound_message_ids:
        for message_id in inbound_message_ids:
            # Imported lazily so the WhatsApp module does not depend on the AI
            # module at import time. The responder re-validates eligibility and
            # acts only when the company and conversation allow it. Scheduling
            # is best-effort: a failure here must never break webhook ingestion.
            try:
                from app.modules.ai_whatsapp.service import process_inbound_message

                process_inbound_message(session=session, message_id=message_id)
            except Exception:
                logger.exception("Failed to schedule AI auto-reply for %s", message_id)
    return {"received": True, "processed": processed}
