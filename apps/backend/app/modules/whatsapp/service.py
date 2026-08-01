import datetime
import hmac
import json
import uuid
from typing import Any, cast

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import asc, desc
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.modules.auth.models import User
from app.modules.companies.models import Company

from .adapters import whatsapp_adapter_registry
from .cloud_api import (
    META_CLOUD_API_ADAPTER,
    CloudApiConnectionInfo,
    MetaCloudApiClient,
    MetaCloudApiError,
    verify_webhook_signature,
)
from .events import whatsapp_event_broker
from .models import (
    IntegrationType,
    MessageDirection,
    MessageStatus,
    WhatsAppCloudApiCreate,
    WhatsAppCloudApiCredentials,
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
    contact = WhatsAppContact(
        company_id=integration.company_id,
        integration_id=integration.id,
        external_id=data.external_id,
        phone_number=data.phone_number,
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
        contact.phone_number = values["phone_number"]
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

    if data.direction == MessageDirection.OUTBOUND and (
        integration.adapter == META_CLOUD_API_ADAPTER
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
        if isinstance(button_reply, dict) and isinstance(button_reply.get("title"), str):
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


def _process_webhook_change(
    *,
    session: Session,
    integration: WhatsAppIntegration,
    value: dict[str, object],
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
            if existing_message is None:
                existing_message = WhatsAppMessage(
                    company_id=integration.company_id,
                    integration_id=integration.id,
                    conversation_id=conversation.id,
                    external_id=external_id,
                    direction=MessageDirection.INBOUND.value,
                    message_type=message_type,
                    content=_message_content(message_payload),
                    media_url=_message_media_reference(message_payload),
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
                existing_message.is_active = True
                existing_message.updated_at = _now()
            session.add(existing_message)
            processed += 1

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
            if status_value in {
                MessageStatus.SENT.value,
                MessageStatus.DELIVERED.value,
                MessageStatus.READ.value,
            } and message.sent_at is None:
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
        raise HTTPException(status_code=400, detail="Invalid Meta webhook JSON") from exc
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
                value = change.get("value")
                if isinstance(value, dict):
                    processed += _process_webhook_change(
                        session=session,
                        integration=integration,
                        value=value,
                    )
    if processed:
        _commit(session)
        for integration in valid_integrations:
            whatsapp_event_broker.publish(
                company_id=integration.company_id,
                event_type="inbox.changed",
                instance_id=integration.id,
            )
    return {"received": True, "processed": processed}
