import datetime
import uuid

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core import security
from app.modules.auth.models import User
from app.modules.auth.service import get_user_by_email

from .models import (
    Company,
    CompanyCreate,
    CompanyUpdate,
    MemberCreate,
    MemberUpdate,
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _ensure_super_admin(user: User) -> None:
    if not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Only super admins can perform this action",
        )


def _get_owned_company(*, session: Session, company_id: uuid.UUID, owner: User) -> Company:
    company = session.get(Company, company_id)
    if not company or company.owner_id != owner.id or not company.is_active:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def create_company(*, session: Session, owner: User, data: CompanyCreate) -> Company:
    _ensure_super_admin(owner)
    company = Company(
        name=data.name,
        owner_id=owner.id,
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def list_companies(*, session: Session, owner: User) -> list[Company]:
    _ensure_super_admin(owner)
    statement = select(Company).where(
        Company.owner_id == owner.id,
        Company.is_active == True,
    )
    return list(session.exec(statement).all())


def get_company(
    *, session: Session, company_id: uuid.UUID, owner: User
) -> Company:
    _ensure_super_admin(owner)
    return _get_owned_company(session=session, company_id=company_id, owner=owner)


def update_company(
    *, session: Session, company_id: uuid.UUID, owner: User, data: CompanyUpdate
) -> Company:
    _ensure_super_admin(owner)
    company = _get_owned_company(session=session, company_id=company_id, owner=owner)
    if data.name is not None:
        company.name = data.name
    company.updated_at = _now()
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def delete_company(*, session: Session, company_id: uuid.UUID, owner: User) -> None:
    _ensure_super_admin(owner)
    company = _get_owned_company(session=session, company_id=company_id, owner=owner)
    company.is_active = False
    company.updated_at = _now()
    session.add(company)
    members = session.exec(
        select(User).where(User.company_id == company.id, User.is_active == True)
    ).all()
    for member in members:
        member.company_id = None
        member.updated_at = _now()
        session.add(member)
    session.commit()


def list_members(
    *, session: Session, company_id: uuid.UUID, owner: User
) -> list[User]:
    _ensure_super_admin(owner)
    _get_owned_company(session=session, company_id=company_id, owner=owner)
    statement = select(User).where(
        User.company_id == company_id,
        User.is_active == True,
    )
    return list(session.exec(statement).all())


def create_member(
    *, session: Session, company_id: uuid.UUID, owner: User, data: MemberCreate
) -> User:
    _ensure_super_admin(owner)
    _get_owned_company(session=session, company_id=company_id, owner=owner)
    if get_user_by_email(session=session, email=str(data.email)):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = security.get_password_hash(data.password)
    member = User(
        email=data.email,
        hashed_password=hashed_password,
        is_active=True,
        is_verified=False,
        is_super_admin=False,
        company_id=company_id,
    )
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def _get_member(
    *, session: Session, company_id: uuid.UUID, member_id: uuid.UUID, owner: User
) -> User:
    _ensure_super_admin(owner)
    _get_owned_company(session=session, company_id=company_id, owner=owner)
    member = session.get(User, member_id)
    if not member or member.company_id != company_id:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


def update_member(
    *,
    session: Session,
    company_id: uuid.UUID,
    member_id: uuid.UUID,
    owner: User,
    data: MemberUpdate,
) -> User:
    member = _get_member(
        session=session, company_id=company_id, member_id=member_id, owner=owner
    )
    if data.email is not None and data.email != member.email:
        existing = get_user_by_email(session=session, email=str(data.email))
        if existing and existing.id != member.id:
            raise HTTPException(status_code=400, detail="Email already registered")
        member.email = data.email
    if data.password is not None:
        member.hashed_password = security.get_password_hash(data.password)
    if data.is_active is not None:
        member.is_active = data.is_active
    member.updated_at = _now()
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def delete_member(
    *,
    session: Session,
    company_id: uuid.UUID,
    member_id: uuid.UUID,
    owner: User,
) -> None:
    member = _get_member(
        session=session, company_id=company_id, member_id=member_id, owner=owner
    )
    member.is_active = False
    member.company_id = None
    member.updated_at = _now()
    session.add(member)
    session.commit()
