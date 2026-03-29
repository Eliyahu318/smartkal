"""Google OAuth token verification and JWT token management."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt

from app.config import get_settings
from app.core.errors import AuthenticationError


def verify_google_token(token: str) -> dict[str, Any]:
    """Verify a Google OAuth2 id_token and return the payload.

    Uses google-auth library's verify_oauth2_token which checks:
    - Token signature against Google's public keys
    - Token expiration
    - Audience matches our client ID
    """
    settings = get_settings()

    if not settings.google_client_id:
        raise AuthenticationError(
            message_he="שירות Google לא מוגדר",
            message_en="Google OAuth not configured",
        )

    try:
        id_info: dict[str, Any] = google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise AuthenticationError(
            message_he="טוקן Google לא תקין",
            message_en="Invalid Google token",
            details={"reason": str(exc)},
        ) from exc

    sub = id_info.get("sub")
    email = id_info.get("email")
    if not sub or not email:
        raise AuthenticationError(
            message_he="טוקן Google חסר פרטים",
            message_en="Google token missing required claims",
        )

    return id_info


def create_access_token(user_id: uuid.UUID) -> str:
    """Create a short-lived JWT access token (default 15 min)."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    token: str = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a long-lived JWT refresh token (default 30 days)."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    token: str = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token


def create_token_pair(user_id: uuid.UUID) -> dict[str, str]:
    """Create both access and refresh tokens."""
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


def decode_token(token: str, *, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT token.

    Raises AuthenticationError if token is invalid, expired, or wrong type.
    """
    settings = get_settings()

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise AuthenticationError(
            message_he="טוקן לא תקין או שפג תוקפו",
            message_en="Invalid or expired token",
            details={"reason": str(exc)},
        ) from exc

    token_type = payload.get("type")
    if token_type != expected_type:
        raise AuthenticationError(
            message_he="סוג טוקן לא תקין",
            message_en="Invalid token type",
            details={"expected": expected_type, "got": token_type},
        )

    sub = payload.get("sub")
    if not sub:
        raise AuthenticationError(
            message_he="טוקן חסר מזהה משתמש",
            message_en="Token missing subject",
        )

    return payload
