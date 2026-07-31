from fastapi import APIRouter, Query
from pydantic import EmailStr
from sqlmodel import Field, SQLModel

from app.utils.deps import AIProtected, CurrentUser, SessionDep

from . import service
from .models import LoginRequest, NewPassword, Token, UserData, UserRegister

router = APIRouter()


class Message(SQLModel):
    """Generic operation result message."""

    message: str = Field(description="Human-readable status message.")


@router.post(
    "/register",
    status_code=201,
    response_model=Message,
    summary="Create a new account",
    description=(
        "Register a regular user with email and password. "
        "A verification token is generated and displayed in the server console. "
        "AI agents are not allowed to call this route."
    ),
    responses={
        400: {"description": "Email already registered"},
        422: {"description": "Missing email or password"},
    },
)
def register_user(
    _: AIProtected,
    user: UserRegister,
    session: SessionDep,
) -> Message:
    service.register_user(session=session, user=user)
    return Message(
        message="User registered successfully. Please check your email to verify your account."
    )


@router.post(
    "/verify-email",
    status_code=200,
    response_model=Token,
    summary="Verify email address",
    description=(
        "Confirm email ownership using the token received at registration. "
        "Returns a JWT access token once verified."
    ),
    responses={400: {"description": "Invalid token or email already verified"}},
)
def verify_email(
    session: SessionDep,
    token: str = Query(
        description="Verification token sent to the user's email.",
        examples=["email-verification-token"],
    ),
) -> Token:
    return service.verify_user_email(session=session, token=token)


@router.post(
    "/resend-verification-email",
    status_code=200,
    response_model=Message,
    summary="Resend verification email",
    description=(
        "Request a new verification token. Always returns success so that "
        "unregistered emails cannot be discovered."
    ),
)
def resend_verification_email(
    session: SessionDep,
    email: EmailStr = Query(  # noqa: B008
        description="Email to resend the verification message to.",
        examples=["user@example.com"],
    ),
) -> Message:
    service.resend_verification_email(session=session, email=email)
    return Message(message="Verification email resent successfully.")


@router.post(
    "/login",
    status_code=200,
    response_model=Token,
    summary="Authenticate user",
    description=(
        "Login with email and password to receive a JWT access token. "
        "Include the token in the `Authorization` header as `Bearer <token>` "
        "for all protected routes."
    ),
    responses={
        401: {"description": "Invalid email or password"},
        403: {"description": "Account deactivated or email not verified"},
    },
)
def login(body: LoginRequest, session: SessionDep) -> Token:
    return service.authenticate_user(
        session=session, email=body.email, password=body.password
    )


@router.post(
    "/recover-password",
    status_code=200,
    response_model=Message,
    summary="Request password recovery",
    description=(
        "Request a password reset token. Always returns success so that "
        "unregistered emails cannot be discovered."
    ),
)
def recover_password(
    session: SessionDep,
    email: EmailStr = Query(  # noqa: B008
        description="Email of the account to recover.",
        examples=["user@example.com"],
    ),
) -> Message:
    service.recover_password(session=session, email=email)
    return Message(message="Password recovery email sent successfully.")


@router.post(
    "/reset-password",
    status_code=200,
    response_model=Message,
    summary="Reset forgotten password",
    description=(
        "Set a new password using the single-use token received via "
        "`POST /auth/recover-password`."
    ),
    responses={400: {"description": "Invalid or expired token"}},
)
def reset_password(
    body: NewPassword,
    session: SessionDep,
) -> Message:
    service.reset_password(session=session, new_password=body)
    return Message(message="Password reset successfully.")


@router.get(
    "/user",
    status_code=200,
    response_model=UserData,
    summary="Get current user profile",
    description=(
        "Return the profile of the authenticated user. Requires a valid JWT "
        "token in the `Authorization` header."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"},
    },
)
def get_current_user_data(current_user: CurrentUser, session: SessionDep) -> UserData:
    return service.get_current_user(session=session, user_id=current_user.id)
