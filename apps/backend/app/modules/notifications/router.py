import uuid

from fastapi import APIRouter, Query

from app.modules.notifications import service
from app.modules.notifications.models import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.utils.deps import CurrentUser, SessionDep

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    session: SessionDep,
    current_user: CurrentUser,
    company_id: uuid.UUID | None = None,
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    return service.list_notifications(
        session=session,
        current_user=current_user,
        company_id=company_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    session: SessionDep,
    current_user: CurrentUser,
    company_id: uuid.UUID | None = None,
) -> UnreadCountResponse:
    return service.unread_count(
        session=session,
        current_user=current_user,
        company_id=company_id,
    )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    session: SessionDep,
    current_user: CurrentUser,
    notification_id: uuid.UUID,
    company_id: uuid.UUID | None = None,
) -> NotificationResponse:
    return service.mark_notification_read(
        session=session,
        current_user=current_user,
        notification_id=notification_id,
        company_id=company_id,
    )


@router.post("/read-all", response_model=dict[str, bool])
def mark_all_notifications_read(
    session: SessionDep,
    current_user: CurrentUser,
    company_id: uuid.UUID | None = None,
) -> dict[str, bool]:
    service.mark_all_notifications_read(
        session=session,
        current_user=current_user,
        company_id=company_id,
    )
    return {"success": True}
