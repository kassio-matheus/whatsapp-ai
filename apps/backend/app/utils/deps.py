from collections.abc import Generator
import hmac
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlmodel import Session

from app.core.config import ai_request_secret, settings
from app.core.db import engine
from app.core.security import ACCESS_TOKEN_PURPOSE, ALGORITHM
from app.modules.auth import TokenPayload, User

bearer_scheme = HTTPBearer(auto_error=False)


BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]


def get_bearer_token(credentials: BearerCredentials) -> str | None:
    if credentials is None:
        return None
    return credentials.credentials


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str | None, Depends(get_bearer_token)]


AI_REQUEST_HEADER = "X-AI-Request"
AI_ACTOR_HEADER = "X-AI-Actor"


def ai_actor_user_id(request: Request) -> str | None:
    """Resolve the acting user id for an internal AI-originated request.

    AI tool calls are authorized natively (no user JWT). The MCP client tags
    the request with ``X-AI-Request`` carrying the server-side secret and
    ``X-AI-Actor`` carrying the user the AI is acting as (e.g. the company
    owner for auto-replies, or the dashboard user for the chat). The secret
    makes the pair unforgeable from outside the process.
    """
    candidate = request.headers.get(AI_REQUEST_HEADER)
    actor = request.headers.get(AI_ACTOR_HEADER)
    if not candidate or not actor:
        return None
    if not hmac.compare_digest(candidate, ai_request_secret()):
        return None
    return actor


def get_current_user(request: Request, session: SessionDep, token: TokenDep) -> User:
    actor = ai_actor_user_id(request)
    if actor:
        user = session.get(User, uuid.UUID(actor) if uuid.UUID(actor) else None)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate AI actor",
            )
        return user
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != ACCESS_TOKEN_PURPOSE:
            raise jwt.InvalidTokenError("Invalid token purpose")
        token_data = TokenPayload(**payload)
    except (jwt.InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_auth(request: Request, token: TokenDep) -> None:
    if ai_actor_user_id(request):
        return
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != ACCESS_TOKEN_PURPOSE:
            raise jwt.InvalidTokenError("Invalid token purpose")
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )


Private = Annotated[None, Depends(require_auth)]


def require_super_admin(current_user: CurrentUser) -> None:
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can perform this action",
        )


SuperAdmin = Annotated[None, Depends(require_super_admin)]


def forbid_ai(request: Request) -> None:
    """Reject requests originated by the AI agent (via the MCP client)."""
    if request.headers.get(AI_REQUEST_HEADER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This route is protected and cannot be accessed by AI agents. "
                "It is permanently unavailable to you. Do not call it again."
            ),
        )


AIProtected = Annotated[None, Depends(forbid_ai)]
