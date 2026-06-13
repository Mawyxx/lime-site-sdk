"""SSE frame parsing for site-login event stream."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from lime_sites._errors import ApiError

_SSE_PATH = "/modules/agent-login/events"


class SseFrameKind(str, Enum):
    KEEPALIVE = "keepalive"
    APPROVED = "approved"
    EXPIRED = "expired"
    ERROR = "error"
    IGNORE = "ignore"


@dataclass(frozen=True, slots=True)
class SseDispatchEvent:
    kind: SseFrameKind
    request_id: str | None = None
    passport: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def parse_sse_json_payload(payload_raw: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        raise ApiError(
            "SSE_INVALID_JSON",
            "Invalid SSE data frame",
            http_status=200,
        ) from exc

    if not isinstance(payload, dict):
        raise ApiError("SSE_INVALID_FRAME", "SSE frame must be a JSON object", http_status=200)
    return payload


def classify_sse_payload(payload: dict[str, Any]) -> SseDispatchEvent:
    frame_type = str(payload.get("type", ""))

    if frame_type == "keepalive":
        return SseDispatchEvent(kind=SseFrameKind.KEEPALIVE)

    if frame_type == "error":
        return SseDispatchEvent(
            kind=SseFrameKind.ERROR,
            error_code=str(payload.get("code", "SSE_ERROR")),
            error_message=str(payload.get("message", "SSE error frame")),
        )

    request_id = str(payload.get("login_request_id", "")).strip()
    if not request_id:
        return SseDispatchEvent(kind=SseFrameKind.IGNORE)

    if frame_type == "expired":
        return SseDispatchEvent(kind=SseFrameKind.EXPIRED, request_id=request_id, passport=None)

    if frame_type == "approved":
        jwt = payload.get("agent_passport_jwt")
        if not jwt or not str(jwt).strip():
            raise ApiError(
                "SSE_APPROVED_INVALID",
                "approved event missing agent_passport_jwt",
                http_status=200,
            )
        return SseDispatchEvent(
            kind=SseFrameKind.APPROVED,
            request_id=request_id,
            passport=str(jwt),
        )

    return SseDispatchEvent(kind=SseFrameKind.IGNORE)


def iter_sse_data_payloads(buffer: str, chunk: str) -> tuple[str, list[str]]:
    """Append chunk to buffer; return updated buffer and complete data payloads."""
    buffer += chunk
    payloads: list[str] = []
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        line = line.rstrip("\r")
        if not line.startswith("data:"):
            continue
        payload_raw = line[5:].lstrip()
        if payload_raw:
            payloads.append(payload_raw)
    return buffer, payloads
