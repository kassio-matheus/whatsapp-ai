import datetime
import hashlib
import secrets
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_PURPOSE = "access"
EMAIL_VERIFICATION_PURPOSE = "email_verification"
PASSWORD_RESET_PURPOSE = "password_reset"
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"not-a-real-password",
    bcrypt.gensalt(),
).decode("utf-8")


def create_access_token(subject: str | Any, expires_delta: datetime.timedelta) -> str:
    now = datetime.datetime.now(datetime.UTC)
    expire = now + expires_delta
    to_encode = {
        "exp": expire,
        "iat": now,
        "nbf": now,
        "sub": str(subject),
        "purpose": ACCESS_TOKEN_PURPOSE,
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, *, purpose: str) -> str | None:
    try:
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if decoded_token.get("purpose") != purpose:
            return None
        return str(decoded_token["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError):
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def dummy_password_hash() -> str:
    return _DUMMY_PASSWORD_HASH
