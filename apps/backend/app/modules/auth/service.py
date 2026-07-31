import datetime
import uuid

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.utils.notifications import Notification, notification

from .models import NewPassword, Token, User, UserData, UserRegister


def get_user_by_email(*, session: Session, email: str) -> User | None:
    """Get user by email."""
    statement = select(User).where(User.email == email.strip().lower())
    session_user = session.exec(statement).first()
    return session_user


def register_user(*, session: Session, user: UserRegister) -> None:
    """Register a regular user; privileged accounts are provisioned separately."""
    if not user.email or not user.password:
        raise HTTPException(
            status_code=422,
            detail="Email and password are required",
        )
    db_user = get_user_by_email(session=session, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )
    hashed_password = security.get_password_hash(user.password)

    db_user = User(
        email=str(user.email).lower(),
        hashed_password=hashed_password,
        is_active=True,
        is_verified=not settings.EMAILS_ENABLED,
        is_super_admin=False,
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    token = security.create_email_verification_token(user.email)
    verification_link = f"{settings.FRONTEND_HOST}/verify-email#token={token}"

    notification.send(
        Notification(
            to=user.email,
            subject=f"Welcome to {settings.PROJECT_NAME}",
            body=f"Verify your email: {verification_link}",
        )
    )


def verify_user_email(*, session: Session, token: str) -> Token:
    """Verify user email."""
    email = security.verify_token(
        token=token,
        purpose=security.EMAIL_VERIFICATION_PURPOSE,
    )
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Invalid token",
        )
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid token")
    if db_user.is_verified:
        raise HTTPException(
            status_code=400,
            detail="Email already verified",
        )
    db_user.is_verified = True
    db_user.updated_at = datetime.datetime.now(datetime.UTC)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    access_token = security.create_access_token(
        subject=db_user.id,
        expires_delta=datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES),
    )
    access_token_obj = Token(
        access_token=access_token,
        token_type="bearer",
    )
    return access_token_obj


def resend_verification_email(*, session: Session, email: str) -> bool:
    """Resend verification email."""
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return True
    if db_user.is_verified:
        return True
    token = security.create_email_verification_token(email=db_user.email)
    verification_link = f"{settings.FRONTEND_HOST}/verify-email#token={token}"

    notification.send(
        Notification(
            to=db_user.email,
            subject=f"Verify your {settings.PROJECT_NAME} account",
            body=f"Verify your email: {verification_link}",
        )
    )
    return True


def authenticate_user(*, session: Session, email: str, password: str) -> Token:
    """Authenticate user and return access token."""
    db_user = get_user_by_email(session=session, email=email)
    password_hash = db_user.hashed_password if db_user else security.dummy_password_hash()
    if not security.verify_password(password, password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not db_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account deactivated",
        )

    if settings.EMAILS_ENABLED and not db_user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    access_token = security.create_access_token(
        subject=db_user.id,
        expires_delta=datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES),
    )

    token = Token(
        access_token=access_token,
        token_type="bearer",
    )
    return token


def recover_password(*, session: Session, email: str) -> bool:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return True

    token = security.generate_password_reset_token()
    db_user.password_reset_token_hash = security.hash_token(token)
    db_user.password_reset_token_expires_at = (
        datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        + datetime.timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    )
    session.add(db_user)
    session.commit()
    reset_link = f"{settings.FRONTEND_HOST}/reset-password#token={token}"

    notification.send(
        Notification(
            to=email,
            subject=f"{settings.PROJECT_NAME} - Password Recovery",
            body=f"Reset your password: {reset_link}",
        )
    )
    return True


def reset_password(*, session: Session, new_password: NewPassword) -> bool:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    token_hash = security.hash_token(new_password.token)
    db_user = session.exec(
        select(User).where(
            User.password_reset_token_hash == token_hash,
            User.password_reset_token_expires_at > now,
        )
    ).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    hashed_password = security.get_password_hash(new_password.password)
    db_user.hashed_password = hashed_password
    db_user.password_reset_token_hash = None
    db_user.password_reset_token_expires_at = None
    db_user.updated_at = datetime.datetime.now(datetime.UTC)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return True


def get_current_user(*, session: Session, user_id: uuid.UUID) -> UserData:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserData(
        email=user.email,
        is_super_admin=user.is_super_admin,
        company_id=user.company_id,
    )
