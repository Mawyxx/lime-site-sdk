from __future__ import annotations

from typing import Any


class LimeError(Exception):
    """Base class for SDK errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.http_status = http_status
        self.detail = detail
        super().__init__(message)


class AuthenticationError(LimeError):
    """Missing or invalid site token."""


class RequestExpiredError(LimeError):
    """Login request expired before agent approval."""


class InvalidPassportError(LimeError):
    """JWT passport verification failed."""


class RateLimitError(LimeError):
    """HTTP 429 — rate limit exceeded."""


class ApiError(LimeError):
    """General API error with code and message."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            http_status=http_status,
            detail=detail,
        )


class TimeoutError(LimeError):
    """wait_for_login exceeded the allotted time without a terminal event."""
