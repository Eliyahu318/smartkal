"""Authentication endpoints: Google OAuth login, token refresh, current user."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Cookie, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import AuthenticationError
from app.core.security import (
    create_token_pair,
    decode_token,
    verify_google_token,
)
from app.db.seed import seed_categories_for_user
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days


def _build_refresh_cookie_header(
    value: str,
    settings: Settings,
    *,
    max_age: int,
) -> str:
    """Build a Set-Cookie header value for the refresh token.

    Starlette's response.set_cookie() does not yet support the CHIPS
    `Partitioned` attribute, so we emit the header manually. Partitioned is
    required for Safari (16.4+) to accept SameSite=None cross-site cookies
    on page refresh without ITP purging them.
    """
    samesite = (settings.cookie_samesite or "lax").lower()
    secure = bool(settings.cookie_secure)
    parts = [
        f"refresh_token={value}",
        "HttpOnly",
        "Path=/api/v1/auth",
        f"Max-Age={max_age}",
        f"SameSite={samesite.capitalize()}",
    ]
    if secure:
        parts.append("Secure")
    # Partitioned is only valid (and only needed) for cross-site cookies,
    # which require SameSite=None; Secure.
    if samesite == "none" and secure:
        parts.append("Partitioned")
    return "; ".join(parts)


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    """Set the refresh token as an httpOnly (optionally Partitioned) cookie."""
    response.headers.append(
        "set-cookie",
        _build_refresh_cookie_header(token, settings, max_age=_COOKIE_MAX_AGE),
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    """Remove the refresh token cookie.

    Mirrors all attributes from _set_refresh_cookie so the browser matches the
    existing cookie and replaces it with an expired one.
    """
    response.headers.append(
        "set-cookie",
        _build_refresh_cookie_header("", settings, max_age=0),
    )


# --- Request / Response schemas ---


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=1, description="Google OAuth2 id_token")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    picture_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# --- Endpoints ---


@router.post("/google", response_model=TokenResponse)
async def google_login(
    body: GoogleLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Verify Google id_token, create or update user, return JWT pair."""
    id_info = verify_google_token(body.id_token)

    google_sub: str = id_info["sub"]
    email: str = id_info["email"]
    name: str = id_info.get("name", email.split("@")[0])
    picture_url: str | None = id_info.get("picture")

    # Find existing user by google_sub
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()

    if user is None:
        # Create new user
        user = User(
            email=email,
            name=name,
            picture_url=picture_url,
            google_sub=google_sub,
        )
        db.add(user)
        await db.flush()  # Get the user.id assigned

        # Seed default categories for new user
        await seed_categories_for_user(db, user.id)

        await logger.ainfo("user_created", user_id=str(user.id), email=email)
    else:
        # Update profile fields from Google (name, picture may change)
        user.name = name
        user.picture_url = picture_url
        await logger.ainfo("user_logged_in", user_id=str(user.id), email=email)

    tokens = create_token_pair(user.id)
    _set_refresh_cookie(response, tokens["refresh_token"], settings)
    return TokenResponse(access_token=tokens["access_token"])


@router.post("/guest", response_model=TokenResponse)
async def guest_login(
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Create a temporary guest user and return JWT pair."""
    guest_id = uuid.uuid4()

    user = User(
        email=f"guest-{guest_id}@smartkal.local",
        name="אורח",
        picture_url=None,
        google_sub=f"guest-{guest_id}",
    )
    db.add(user)
    await db.flush()

    await seed_categories_for_user(db, user.id)
    await db.commit()

    await logger.ainfo("guest_user_created", user_id=str(user.id))

    tokens = create_token_pair(user.id)
    _set_refresh_cookie(response, tokens["refresh_token"], settings)
    return TokenResponse(access_token=tokens["access_token"])


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Exchange a valid refresh token (from httpOnly cookie) for a new token pair."""
    if not refresh_token:
        raise AuthenticationError(
            message_he="לא נמצא טוקן רענון",
            message_en="No refresh token provided",
        )

    payload = decode_token(refresh_token, expected_type="refresh")
    user_id = payload["sub"]

    try:
        uid = uuid.UUID(user_id)
    except ValueError as exc:
        raise AuthenticationError(
            message_he="מזהה משתמש לא תקין",
            message_en="Invalid user ID in token",
        ) from exc

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthenticationError(
            message_he="משתמש לא נמצא או אינו פעיל",
            message_en="User not found or deactivated",
        )

    tokens = create_token_pair(user.id)
    _set_refresh_cookie(response, tokens["refresh_token"], settings)
    return TokenResponse(access_token=tokens["access_token"])


@router.post("/logout")
async def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Clear the refresh token cookie."""
    _clear_refresh_cookie(response, settings)
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Return the currently authenticated user's profile."""
    return current_user
