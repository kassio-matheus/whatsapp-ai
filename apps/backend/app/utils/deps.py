from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlmodel import Session

from app.core.config import settings
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


def get_current_user(session: SessionDep, token: TokenDep) -> User:
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


def require_auth(token: TokenDep) -> None:
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


AI_REQUEST_HEADER = "X-AI-Request"


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
