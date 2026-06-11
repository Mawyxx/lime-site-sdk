from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from lime_sites._client import LimeSiteClient
from lime_sites._errors import ApiError, RequestExpiredError, TimeoutError
from lime_sites._sse import listen_for_events


def _sse_line(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


def _make_client(chunks: list[bytes]) -> LimeSiteClient:
    index = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Accept") == "text/event-stream"
        assert request.headers.get("X-Site-Token") == "st_test"

        async def body():
            while index["i"] < len(chunks):
                yield chunks[index["i"]]
                index["i"] += 1

        return httpx.Response(200, content=body())

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=http_client,
    )


@pytest.mark.asyncio
async def test_keepalive_then_approved() -> None:
    client = _make_client(
        [
            _sse_line({"type": "keepalive"}),
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "status": "approved",
                    "agent_passport_jwt": "jwt.token.here",
                },
            ),
        ],
    )
    result = await listen_for_events(client, "lr_1", timeout=5.0)
    assert result.request_id == "lr_1"
    assert result.agent_passport_jwt == "jwt.token.here"
    await client.aclose()


@pytest.mark.asyncio
async def test_ignores_unrelated_approved() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_other",
                    "status": "approved",
                    "agent_passport_jwt": "other.jwt",
                },
            ),
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "status": "approved",
                    "agent_passport_jwt": "target.jwt",
                },
            ),
        ],
    )
    result = await listen_for_events(client, "lr_1", timeout=5.0)
    assert result.agent_passport_jwt == "target.jwt"
    await client.aclose()


@pytest.mark.asyncio
async def test_expired_raises() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "expired",
                    "login_request_id": "lr_1",
                    "status": "expired",
                },
            ),
        ],
    )
    with pytest.raises(RequestExpiredError):
        await listen_for_events(client, "lr_1", timeout=5.0)
    await client.aclose()


@pytest.mark.asyncio
async def test_error_frame_raises_api_error() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "error",
                    "code": "SITE_LOGIN_EVENT_CHANNEL_UNAVAILABLE",
                    "message": "channel down",
                },
            ),
        ],
    )
    with pytest.raises(ApiError) as exc:
        await listen_for_events(client, "lr_1", timeout=5.0)
    assert exc.value.code == "SITE_LOGIN_EVENT_CHANNEL_UNAVAILABLE"
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_json_raises() -> None:
    client = _make_client([b"data: not-json\n\n"])
    with pytest.raises(ApiError, match="Invalid SSE"):
        await listen_for_events(client, "lr_1", timeout=5.0)
    await client.aclose()


@pytest.mark.asyncio
async def test_non_object_frame_raises() -> None:
    client = _make_client([b"data: []\n\n"])
    with pytest.raises(ApiError, match="JSON object"):
        await listen_for_events(client, "lr_1", timeout=5.0)
    await client.aclose()


@pytest.mark.asyncio
async def test_approved_missing_jwt_raises() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "status": "approved",
                },
            ),
        ],
    )
    with pytest.raises(ApiError, match="agent_passport_jwt"):
        await listen_for_events(client, "lr_1", timeout=5.0)
    await client.aclose()


@pytest.mark.asyncio
async def test_sse_http_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"unavailable")

    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ApiError) as exc:
        await listen_for_events(client, "lr_1", timeout=1.0, backoff_base=0.01)
    assert exc.value.code == "SSE_HTTP_ERROR"
    await client.aclose()


@pytest.mark.asyncio
async def test_timeout_when_no_terminal_event() -> None:
    client = _make_client([_sse_line({"type": "keepalive"})])
    with pytest.raises(TimeoutError, match="Timed out"):
        await listen_for_events(client, "lr_1", timeout=0.15, backoff_base=0.05)
    await client.aclose()


@pytest.mark.asyncio
async def test_reconnect_after_disconnect() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:

            async def fail_body():
                yield _sse_line({"type": "keepalive"})
                raise httpx.ReadError("connection reset")

            return httpx.Response(200, content=fail_body())

        async def ok_body():
            yield _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "status": "approved",
                    "agent_passport_jwt": "jwt.after.reconnect",
                },
            )

        return httpx.Response(200, content=ok_body())

    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await listen_for_events(client, "lr_1", timeout=5.0, backoff_base=0.01)
    assert result.agent_passport_jwt == "jwt.after.reconnect"
    assert calls["n"] >= 2
    await client.aclose()


@pytest.mark.asyncio
async def test_redirect_url_parsed() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "status": "approved",
                    "agent_passport_jwt": "jwt.token",
                    "redirect_url": "https://site.example/callback",
                },
            ),
        ],
    )
    result = await listen_for_events(client, "lr_1", timeout=5.0)
    assert result.redirect_url == "https://site.example/callback"
    await client.aclose()


@pytest.mark.asyncio
async def test_empty_data_payload_skipped() -> None:
    client = _make_client([b"data:\n\n", _sse_line({"type": "keepalive"})])
    with pytest.raises(TimeoutError):
        await listen_for_events(client, "lr_1", timeout=0.1, backoff_base=0.01)
    await client.aclose()


@pytest.mark.asyncio
async def test_unknown_frame_type_ignored() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "challenge",
                    "login_request_id": "lr_1",
                    "pow_challenge": "x",
                    "pow_difficulty": 8,
                },
            ),
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "status": "approved",
                    "agent_passport_jwt": "jwt.ok",
                },
            ),
        ],
    )
    result = await listen_for_events(client, "lr_1", timeout=5.0)
    assert result.agent_passport_jwt == "jwt.ok"
    await client.aclose()


@pytest.mark.asyncio
async def test_timeout_breaks_when_remaining_zero_after_stream() -> None:
    times = iter([0.0, 0.0, 0.0, 1.0])

    def fake_monotonic() -> float:
        return next(times)

    client = _make_client([_sse_line({"type": "keepalive"})])
    with patch("lime_sites._sse.time.monotonic", side_effect=fake_monotonic):
        with pytest.raises(TimeoutError):
            await listen_for_events(client, "lr_1", timeout=1.0, backoff_base=0.01)
    await client.aclose()


@pytest.mark.asyncio
async def test_timeout_breaks_before_stream_when_deadline_elapsed() -> None:
    times = iter([0.0, 0.5, 1.0])

    def fake_monotonic() -> float:
        return next(times)

    client = _make_client([_sse_line({"type": "keepalive"})])
    with patch("lime_sites._sse.time.monotonic", side_effect=fake_monotonic):
        with pytest.raises(TimeoutError):
            await listen_for_events(client, "lr_1", timeout=1.0, backoff_base=0.01)
    await client.aclose()
