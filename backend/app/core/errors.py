"""Structured error hierarchy with Hebrew messages and request tracing."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any


class SmartKalError(Exception):
    """Base exception for all SmartKal application errors."""

    error_code: str = "SMARTKAL_ERROR"
    message_he: str = "אירעה שגיאה"
    message_en: str = "An error occurred"
    status_code: int = 500

    def __init__(
        self,
        *,
        message_he: str | None = None,
        message_en: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if message_he is not None:
            self.message_he = message_he
        if message_en is not None:
            self.message_en = message_en
        self.details = details or {}
        self.source_location = self._capture_source()
        self.timestamp = datetime.now(timezone.utc).isoformat()
        super().__init__(self.message_en)

    @staticmethod
    def _capture_source() -> str:
        """Capture the file:line where the exception was raised."""
        frame = inspect.currentframe()
        # Walk up: _capture_source -> __init__ -> caller
        if frame and frame.f_back and frame.f_back.f_back:
            caller = frame.f_back.f_back
            return f"{caller.f_code.co_filename}:{caller.f_lineno}"
        return "unknown"

    def to_dict(self, *, request_id: str = "") -> dict[str, Any]:
        return {
            "error": {
                "code": self.error_code,
                "message": self.message_he,
                "message_en": self.message_en,
                "details": self.details,
                "debug": {
                    "timestamp": self.timestamp,
                    "request_id": request_id,
                    "source": self.source_location,
                },
            }
        }


# --- Concrete error subclasses ---


class ValidationError(SmartKalError):
    error_code = "VALIDATION_ERROR"
    message_he = "הנתונים שהוזנו אינם תקינים"
    message_en = "Validation error"
    status_code = 422


class AuthenticationError(SmartKalError):
    error_code = "AUTHENTICATION_ERROR"
    message_he = "נדרשת התחברות"
    message_en = "Authentication required"
    status_code = 401


class NotFoundError(SmartKalError):
    error_code = "NOT_FOUND"
    message_he = "הפריט לא נמצא"
    message_en = "Resource not found"
    status_code = 404


class RateLimitError(SmartKalError):
    error_code = "RATE_LIMIT"
    message_he = "יותר מדי בקשות, נסה שוב מאוחר יותר"
    message_en = "Rate limit exceeded"
    status_code = 429


class ExternalServiceError(SmartKalError):
    error_code = "EXTERNAL_SERVICE_ERROR"
    message_he = "שגיאה בשירות חיצוני"
    message_en = "External service error"
    status_code = 502


class ReceiptParsingError(SmartKalError):
    error_code = "RECEIPT_PARSING_ERROR"
    message_he = "לא ניתן לעבד את הקבלה"
    message_en = "Receipt parsing failed"
    status_code = 422


class ClaudeAPIError(ExternalServiceError):
    error_code = "CLAUDE_API_ERROR"
    message_he = "שגיאה בשירות Claude AI"
    message_en = "Claude API error"
    status_code = 502


class SuperGETError(ExternalServiceError):
    error_code = "SUPERGET_ERROR"
    message_he = "שגיאה בשירות השוואת מחירים"
    message_en = "SuperGET API error"
    status_code = 502


class DatabaseError(SmartKalError):
    error_code = "DATABASE_ERROR"
    message_he = "שגיאת מסד נתונים"
    message_en = "Database error"
    status_code = 500
