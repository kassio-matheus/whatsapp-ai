import uuid

from fastapi import APIRouter

from app.utils.deps import CurrentUser, SessionDep, SuperAdmin

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
    return CompanyResponse(
        id=company.id,
        name=company.name,
        is_active=company.is_active,
        created_at=company.created_at,
        owner_id=company.owner_id,
    )


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
) -> list[CompanyResponse]:
    companies = service.list_companies(session=session, owner=current_user)
    return [
        CompanyResponse(
            id=c.id,
            name=c.name,
            is_active=c.is_active,
            created_at=c.created_at,
            owner_id=c.owner_id,
        )
        for c in companies
    ]


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
    return CompanyResponse(
        id=company.id,
        name=company.name,
        is_active=company.is_active,
        created_at=company.created_at,
        owner_id=company.owner_id,
    )


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
    return CompanyResponse(
        id=company.id,
        name=company.name,
        is_active=company.is_active,
        created_at=company.created_at,
        owner_id=company.owner_id,
    )


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
    return MemberResponse(
        id=member.id,
        email=member.email,
        is_active=member.is_active,
        is_verified=member.is_verified,
        is_super_admin=member.is_super_admin,
        company_id=member.company_id,
        created_at=member.created_at,
    )


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
) -> list[MemberResponse]:
    members = service.list_members(
        session=session, company_id=company_id, owner=current_user
    )
    return [
        MemberResponse(
            id=m.id,
            email=m.email,
            is_active=m.is_active,
            is_verified=m.is_verified,
            is_super_admin=m.is_super_admin,
            company_id=m.company_id,
            created_at=m.created_at,
        )
        for m in members
    ]


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
    return MemberResponse(
        id=member.id,
        email=member.email,
        is_active=member.is_active,
        is_verified=member.is_verified,
        is_super_admin=member.is_super_admin,
        company_id=member.company_id,
        created_at=member.created_at,
    )


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
