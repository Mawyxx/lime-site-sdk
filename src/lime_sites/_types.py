from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True, slots=True)
class LoginRequestResult:
    """Response from ``create_login_request()``.

    Attributes:
        request_id: Hand this to the agent worker (maps from API ``login_request_id``).
        status: Initial status (typically ``PENDING``).
        expires_at: When the request expires if not approved.
    """

    request_id: str
    status: str
    expires_at: datetime

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> LoginRequestResult:
        return cls(
            request_id=str(data["login_request_id"]),
            status=str(data["status"]),
            expires_at=_parse_datetime(str(data["expires_at"])),
        )


@dataclass(frozen=True, slots=True)
class LoginResult:
    request_id: str
    agent_passport_jwt: str
    redirect_url: str | None = None

    @classmethod
    def from_sse(cls, data: dict[str, Any]) -> LoginResult:
        jwt = data.get("agent_passport_jwt")
        if not jwt or not str(jwt).strip():
            raise ValueError("approved event missing agent_passport_jwt")
        redirect = data.get("redirect_url")
        return cls(
            request_id=str(data["login_request_id"]),
            agent_passport_jwt=str(jwt),
            redirect_url=str(redirect) if redirect else None,
        )


@dataclass(frozen=True, slots=True)
class BindingRequestResult:
    """Response from ``create_binding_request()``.

    Attributes:
        binding_id: Persist server-side with your user session before redirecting.
        connect_url: Hosted portal URL from the API — redirect the browser here.
        status: Initial status (typically ``PENDING``).
        expires_at: When the binding request expires if not completed.
    """

    binding_id: str
    connect_url: str
    status: str
    expires_at: datetime

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> BindingRequestResult:
        return cls(
            binding_id=str(data["binding_id"]),
            connect_url=str(data["connect_url"]),
            status=str(data["status"]),
            expires_at=_parse_datetime(str(data["expires_at"])),
        )


@dataclass(frozen=True, slots=True)
class PassportVerificationResult:
    """Outcome of ``verify_passport()`` / ``verify_binding_passport()``.

    Attributes:
        valid: ``True`` when JWT signature, aud, exp, and claim binding OK.
        claims: Decoded JWT payload (includes ``sub`` → ``agent_id``, ``user_id``).
    """

    valid: bool
    claims: dict[str, Any]
