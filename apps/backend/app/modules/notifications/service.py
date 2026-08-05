import datetime
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlmodel import Session

from app.modules.auth.models import User
from app.modules.notifications.models import (
    Notification,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.modules.whatsapp.models import (
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppMessage,
)
from app.modules.whatsapp.service import _accessible_company_ids, _ensure_company_access

#: Message kinds that surface as operator notifications. Status/system updates
#: and internal notes are filtered out to avoid noise.
NOTIFIABLE_MESSAGE_TYPES = frozenset(
    {
        "text",
        "image",
        "video",
        "audio",
        "document",
        "location",
        "contacts",
        "interactive",
        "sticker",
    }
)

#: Minimum gap between two notifications for the same conversation. A second
#: inbound message while the operator is away is an error of the same kind the
#: first one already surfaced; pushing a new notification for it only adds
#: noise. The latest message is reachable from the conversation itself.
RATE_LIMIT_WINDOW = datetime.timedelta(minutes=10)

NOTIFICATION_TYPE_MESSAGE = "whatsapp.message"


def _message_preview(message: WhatsAppMessage) -> str:
    if message.message_type == "text" and message.content:
        return message.content[:200]
    return f"[{message.message_type}]"


def create_message_notifications(
    *,
    session: Session,
    message_ids: list[uuid.UUID],
) -> int:
    """Create in-app notifications for freshly persisted inbound messages.

    Only notifiable inbound message types are surfaced, one per conversation
    inside the rate-limit window, so a burst of replies produces a single
    notification instead of a stream. Returns the number created.
    """
    created = 0
    for message_id in message_ids:
        message = session.get(WhatsAppMessage, message_id)

        if message is None or not message.is_active:
            continue
        if message.direction != "inbound":
            continue
        if message.message_type not in NOTIFIABLE_MESSAGE_TYPES:
            continue
        if _recent_unread_for_conversation(
            session=session,
            company_id=message.company_id,
            conversation_id=message.conversation_id,
        ):
            continue

        conversation = session.get(
            WhatsAppConversation, message.conversation_id)
        contact_name: str | None = None
        if conversation is not None and conversation.contact_id is not None:
            contact = session.get(WhatsAppContact, conversation.contact_id)
            if contact is not None and contact.name:
                contact_name = contact.name

        notification = Notification(
            company_id=message.company_id,
            type=NOTIFICATION_TYPE_MESSAGE,
            title=contact_name or "Nova mensagem no WhatsApp",
            body=_message_preview(message),
            conversation_id=message.conversation_id,
            integration_id=message.integration_id,
            message_id=message.id,
        )
        session.add(notification)
        created += 1

    if created:
        session.commit()
    return created


def _recent_unread_for_conversation(
    *,
    session: Session,
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> bool:
    cutoff = (
        datetime.datetime.now(datetime.UTC).replace(
            tzinfo=None) - RATE_LIMIT_WINDOW
    )
    existing = session.exec(
        select(Notification).where(
            Notification.company_id == company_id,
            Notification.conversation_id == conversation_id,
            Notification.is_read.is_(False),
            Notification.created_at >= cutoff,
        )
    ).scalars().first()
    return existing is not None


def _resolve_company_id(
    *,
    session: Session,
    current_user: User,
    company_id: uuid.UUID | None,
) -> uuid.UUID:
    if company_id is not None:
        _ensure_company_access(
            session=session,
            company_id=company_id,
            current_user=current_user,
        )
        return company_id
    company_ids = _accessible_company_ids(
        session=session,
        current_user=current_user,
        company_id=None,
    )
    if not company_ids:
        raise HTTPException(
            status_code=404, detail="Nenhuma empresa encontrada.")
    if len(company_ids) > 1:
        raise HTTPException(
            status_code=400,
            detail="company_id é obrigatório para usuários com acesso a várias empresas.",
        )
    return company_ids[0]


def list_notifications(
    *,
    session: Session,
    current_user: User,
    company_id: uuid.UUID | None = None,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> NotificationListResponse:
    resolved = _resolve_company_id(
        session=session, current_user=current_user, company_id=company_id)
    conditions = [Notification.company_id == resolved]
    if unread_only:
        conditions.append(Notification.is_read.is_(False))

    items = session.exec(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    unread_count = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(Notification.company_id == resolved, Notification.is_read.is_(False))
    ).scalar_one()

    return NotificationListResponse(
        items=[_notification_response(item) for item in items],
        unread_count=unread_count,
    )


def unread_count(
    *,
    session: Session,
    current_user: User,
    company_id: uuid.UUID | None = None,
) -> UnreadCountResponse:

    if (company_id is None):
        raise HTTPException(
            status_code=404,
            detail="Company ID is required to fetch unread count.",
        )

    resolved = _resolve_company_id(
        session=session, current_user=current_user, company_id=company_id)

    count = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(Notification.company_id == resolved, Notification.is_read.is_(False))
    ).scalar_one()

    return UnreadCountResponse(unread_count=count)


def _get_notification(
    *,
    session: Session,
    current_user: User,
    company_id: uuid.UUID | None,
    notification_id: uuid.UUID,
) -> Notification:
    resolved = _resolve_company_id(
        session=session, current_user=current_user, company_id=company_id)
    notification = session.get(Notification, notification_id)
    if notification is None or notification.company_id != resolved:
        raise HTTPException(
            status_code=404, detail="Notification not found.")
    return notification


def mark_notification_read(
    *,
    session: Session,
    current_user: User,
    notification_id: uuid.UUID,
    company_id: uuid.UUID | None = None,
) -> NotificationResponse:
    notification = _get_notification(
        session=session,
        current_user=current_user,
        company_id=company_id,
        notification_id=notification_id,
    )
    if not notification.is_read:
        notification.is_read = True
        session.add(notification)
        session.commit()
        session.refresh(notification)
    return _notification_response(notification)


def mark_all_notifications_read(
    *,
    session: Session,
    current_user: User,
    company_id: uuid.UUID | None = None,
) -> None:
    resolved = _resolve_company_id(
        session=session, current_user=current_user, company_id=company_id)
    notifications = session.exec(
        select(Notification).where(
            Notification.company_id == resolved,
            Notification.is_read.is_(False),
        )
    ).scalars().all()
    for notification in notifications:
        notification.is_read = True
    if notifications:
        session.add_all(notifications)
        session.commit()


def _notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        conversation_id=notification.conversation_id,
        integration_id=notification.integration_id,
        message_id=notification.message_id,
        is_read=notification.is_read,
        created_at=notification.created_at,
    )
