import uuid

from fastapi import APIRouter, Query

from app.utils.deps import CurrentUser, SessionDep, SuperAdmin
from app.utils.timezone import to_company_timezone

from . import service
from .models import (
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    MemberCreate,
    MemberResponse,
    MemberUpdate,
)

router = APIRouter()


def _company_response(company) -> CompanyResponse:
    timezone = company.timezone or "UTC"
    return CompanyResponse(
        id=company.id,
        name=company.name,
        timezone=timezone,
        is_active=company.is_active,
        created_at=to_company_timezone(company.created_at, timezone),
        updated_at=to_company_timezone(company.updated_at, timezone),
        owner_id=company.owner_id,
    )


def _member_response(member, timezone: str = "UTC") -> MemberResponse:
    return MemberResponse(
        id=member.id,
        email=member.email,
        is_active=member.is_active,
        is_verified=member.is_verified,
        is_super_admin=member.is_super_admin,
        company_id=member.company_id,
        created_at=to_company_timezone(member.created_at, timezone),
    )


@router.post(
    "",
    status_code=201,
    response_model=CompanyResponse,
    summary="Create a company",
    description="Create a new company owned by the current super admin.",
)
def create_company(
    data: CompanyCreate,
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
) -> CompanyResponse:
    company = service.create_company(
        session=session, owner=current_user, data=data
    )
    return _company_response(company)


@router.get(
    "",
    response_model=list[CompanyResponse],
    summary="List companies",
    description="List all companies owned by the current super admin.",
)
def list_companies(
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
    name: str | None = Query(
        default=None,
        description="Filter companies by name (case-insensitive partial match).",
        json_schema_extra={"examples": ["Acme"]},
    ),
    is_active: bool | None = Query(
        default=None, description="Filter by active status."
    ),
) -> list[CompanyResponse]:
    companies = service.list_companies(
        session=session,
        owner=current_user,
        name=name,
        is_active=is_active,
    )
    return [_company_response(c) for c in companies]


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get company",
    description="Return a single company owned by the current super admin.",
    operation_id="get_company_by_id",
)
def get_company(
    company_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
) -> CompanyResponse:
    company = service.get_company(
        session=session, company_id=company_id, owner=current_user
    )
    return _company_response(company)


@router.put(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Update company",
    description="Edit a company owned by the current super admin.",
)
def update_company(
    company_id: uuid.UUID,
    data: CompanyUpdate,
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
) -> CompanyResponse:
    company = service.update_company(
        session=session, company_id=company_id, owner=current_user, data=data
    )
    return _company_response(company)


@router.delete(
    "/{company_id}",
    status_code=204,
    summary="Delete company",
    description="Soft-delete a company owned by the current super admin.",
)
def delete_company(
    company_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
) -> None:
    service.delete_company(
        session=session, company_id=company_id, owner=current_user
    )


@router.post(
    "/{company_id}/members",
    status_code=201,
    response_model=MemberResponse,
    summary="Create a member",
    description="Register a new member (non-super-admin) in a company.",
)
def create_member(
    company_id: uuid.UUID,
    data: MemberCreate,
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
) -> MemberResponse:
    member = service.create_member(
        session=session,
        company_id=company_id,
        owner=current_user,
        data=data,
    )
    return _member_response(member)


@router.get(
    "/{company_id}/members",
    response_model=list[MemberResponse],
    summary="List members",
    description="List all active members of a company.",
)
def list_members(
    company_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
    email: str | None = Query(
        default=None,
        description="Filter members by email (case-insensitive partial match).",
        json_schema_extra={"examples": ["john@"]},
    ),
    is_active: bool | None = Query(
        default=None, description="Filter by active status."
    ),
) -> list[MemberResponse]:
    timezone = service.get_company(
        session=session, company_id=company_id, owner=current_user
    ).timezone or "UTC"
    members = service.list_members(
        session=session,
        company_id=company_id,
        owner=current_user,
        email=email,
        is_active=is_active,
    )
    return [_member_response(m, timezone) for m in members]


@router.put(
    "/{company_id}/members/{member_id}",
    response_model=MemberResponse,
    summary="Update member",
    description="Edit a member of a company (email, password or active status).",
)
def update_member(
    company_id: uuid.UUID,
    member_id: uuid.UUID,
    data: MemberUpdate,
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
) -> MemberResponse:
    member = service.update_member(
        session=session,
        company_id=company_id,
        member_id=member_id,
        owner=current_user,
        data=data,
    )
    timezone = service.get_company(
        session=session, company_id=company_id, owner=current_user
    ).timezone or "UTC"
    return _member_response(member, timezone)


@router.delete(
    "/{company_id}/members/{member_id}",
    status_code=204,
    summary="Delete member",
    description="Soft-delete a member of a company.",
)
def delete_member(
    company_id: uuid.UUID,
    member_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    _: SuperAdmin,
) -> None:
    service.delete_member(
        session=session,
        company_id=company_id,
        member_id=member_id,
        owner=current_user,
    )
