"""FastAPI dependencies for authentication and database access."""

from __future__ import annotations

import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, NotFoundError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT from Authorization header, return the User.

    Raises AuthenticationError if no token, invalid token, or user not found.
    """
    if credentials is None:
        raise AuthenticationError(
            message_he="נדרשת התחברות",
            message_en="Authentication required",
        )

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = payload["sub"]

    try:
        uid = uuid.UUID(user_id)
    except ValueError as exc:
        raise AuthenticationError(
            message_he="מזהה משתמש לא תקין",
            message_en="Invalid user ID in token",
        ) from exc

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError(
            message_he="משתמש לא נמצא",
            message_en="User not found",
        )

    if not user.is_active:
        raise AuthenticationError(
            message_he="חשבון המשתמש אינו פעיל",
            message_en="User account is deactivated",
        )

    return user
