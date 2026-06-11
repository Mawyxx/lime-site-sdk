from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from lime_sites._client import LimeSiteClient
from lime_sites._errors import ApiError, RequestExpiredError, TimeoutError
from lime_sites._types import LoginResult

logger = logging.getLogger("lime")

_SSE_PATH = "/modules/agent-login/events"


async def listen_for_events(
    client: LimeSiteClient,
    request_id: str,
    *,
    timeout: float = 120.0,
    backoff_base: float = 0.5,
) -> LoginResult:
    """Listen on site-login SSE until approved, expired, or timeout."""
    deadline = time.monotonic() + timeout
    backoff = backoff_base
    buffer = ""

    while time.monotonic() < deadline:
        if _remaining(deadline) <= 0:
            break

        try:
            async with client.stream(_SSE_PATH) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ApiError(
                        "SSE_HTTP_ERROR",
                        f"SSE stream failed (HTTP {response.status_code})",
                        http_status=response.status_code,
                        detail={"body": body.decode(errors="replace")[:200]},
                    )

                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.rstrip("\r")
                        if not line.startswith("data:"):
                            continue
                        payload_raw = line[5:].lstrip()
                        if not payload_raw:
                            continue
                        result = _handle_frame(payload_raw, request_id)
                        if result is not None:
                            return result
        except (ApiError, RequestExpiredError):
            raise
        except Exception as exc:
            logger.warning("SSE connection dropped: %s", exc)

        if _remaining(deadline) <= 0:
            break

        sleep_for = min(backoff, _remaining(deadline))
        logger.debug("SSE reconnect in %.2fs", sleep_for)
        await _sleep(sleep_for)
        backoff = min(backoff * 2, 8.0)

    raise TimeoutError(
        f"Timed out waiting for login approval after {timeout:.0f}s",
        code="LOGIN_WAIT_TIMEOUT",
    )


def _handle_frame(payload_raw: str, request_id: str) -> LoginResult | None:
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

    frame_type = str(payload.get("type", ""))

    if frame_type == "keepalive":
        return None

    if frame_type == "error":
        raise ApiError(
            str(payload.get("code", "SSE_ERROR")),
            str(payload.get("message", "SSE error frame")),
            http_status=200,
        )

    event_id = str(payload.get("login_request_id", ""))
    if event_id != request_id:
        return None

    if frame_type == "expired":
        raise RequestExpiredError(
            f"Login request {request_id} expired",
            code="SITE_LOGIN_REQUEST_EXPIRED",
        )

    if frame_type == "approved":
        try:
            return LoginResult.from_sse(payload)
        except ValueError as exc:
            raise ApiError(
                "SSE_APPROVED_INVALID",
                str(exc),
                http_status=200,
            ) from exc

    return None


def _remaining(deadline: float) -> float:
    return deadline - time.monotonic()


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)
