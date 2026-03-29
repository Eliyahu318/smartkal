"""Authentication endpoints: Google OAuth login, token refresh, current user."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


# --- Request / Response schemas ---


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=1, description="Google OAuth2 id_token")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


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
    db: AsyncSession = Depends(get_db),
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
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair."""
    payload = decode_token(body.refresh_token, expected_type="refresh")
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
    return TokenResponse(**tokens)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Return the currently authenticated user's profile."""
    return current_user
