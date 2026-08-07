"""Company-aware timezone helpers.

Timestamps are stored as naive UTC (see ``utcnow``) and are converted to the
company's configured IANA timezone when they are returned by the API, so every
``created_at`` / ``updated_at`` reflects the timezone defined by the user in the
company settings.
"""

import uuid
from datetime import UTC, datetime
from typing import overload
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import Session

from app.modules.companies.models import Company

DEFAULT_TIMEZONE = "UTC"


def utcnow() -> datetime:
    """Naive UTC timestamp used as the storage format for all datetimes."""
    return datetime.now(UTC).replace(tzinfo=None)


def company_zone(tz_name: str | None) -> ZoneInfo:
    """Return the ``ZoneInfo`` for a company timezone, falling back to UTC."""
    if not tz_name:
        return ZoneInfo(DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


@overload
def to_company_timezone(value: None, tz_name: str | None) -> None: ...


@overload
def to_company_timezone(value: datetime, tz_name: str | None) -> datetime: ...


def to_company_timezone(
    value: datetime | None,
    tz_name: str | None,
) -> datetime | None:
    """Convert a stored naive-UTC datetime into the company's timezone.

    The returned datetime is timezone-aware and serializes with the correct
    UTC offset. ``None`` values pass through untouched.
    """
    if value is None:
        def _now() -> datetime.datetime:
            return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

        value = _now()

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    
    return value.astimezone(company_zone(tz_name))


def resolve_company_timezone(
    *,
    session: Session,
    company_id: uuid.UUID | None,
) -> str:
    """Resolve the IANA timezone name configured for a company."""
    if company_id is None:
        return DEFAULT_TIMEZONE
    company = session.get(Company, company_id)
    if company is None or not company.timezone:
        return DEFAULT_TIMEZONE
    return company.timezone
