from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from lime_sites._client import LimeSiteClient
from lime_sites._dispatcher import SiteEventDispatcher
from lime_sites._sse import SseDispatchEvent, SseFrameKind


def _sse_line(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


def _make_client(chunks: list[bytes]) -> LimeSiteClient:
    index = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Accept") == "text/event-stream"

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
async def test_dispatcher_approved_invokes_handler() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "agent_passport_jwt": "jwt.here",
                },
            ),
        ],
    )
    handlers: list[tuple[str, str | None]] = []

    async def capture(request_id: str, passport: str | None) -> None:
        handlers.append((request_id, passport))

    dispatcher = SiteEventDispatcher(client, [capture], backoff_base=0.01)
    asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.2), timeout=1.0)
    await dispatcher.stop()
    await client.aclose()

    assert handlers == [("lr_1", "jwt.here")]


@pytest.mark.asyncio
async def test_dispatcher_expired_passport_none() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "expired",
                    "login_request_id": "lr_exp",
                },
            ),
        ],
    )
    handlers: list[tuple[str, str | None]] = []

    async def capture(request_id: str, passport: str | None) -> None:
        handlers.append((request_id, passport))

    dispatcher = SiteEventDispatcher(client, [capture], backoff_base=0.01)
    asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.2), timeout=1.0)
    await dispatcher.stop()
    await client.aclose()

    assert handlers == [("lr_exp", None)]


@pytest.mark.asyncio
async def test_dispatcher_multiple_handlers() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "agent_passport_jwt": "jwt.multi",
                },
            ),
        ],
    )
    calls = {"a": 0, "b": 0}

    async def handler_a(request_id: str, passport: str | None) -> None:
        calls["a"] += 1

    async def handler_b(request_id: str, passport: str | None) -> None:
        calls["b"] += 1

    dispatcher = SiteEventDispatcher(client, [handler_a, handler_b], backoff_base=0.01)
    asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.2), timeout=1.0)
    await dispatcher.stop()
    await client.aclose()

    assert calls == {"a": 1, "b": 1}


@pytest.mark.asyncio
async def test_dispatcher_handler_error_continues() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_1",
                    "agent_passport_jwt": "jwt.first",
                },
            ),
            _sse_line(
                {
                    "type": "approved",
                    "login_request_id": "lr_2",
                    "agent_passport_jwt": "jwt.second",
                },
            ),
        ],
    )
    seen: list[str] = []

    async def bad_handler(request_id: str, passport: str | None) -> None:
        if request_id == "lr_1":
            raise RuntimeError("handler boom")
        seen.append(request_id)

    dispatcher = SiteEventDispatcher(client, [bad_handler], backoff_base=0.01)
    asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.3), timeout=2.0)
    await dispatcher.stop()
    await client.aclose()

    assert seen == ["lr_2"]


@pytest.mark.asyncio
async def test_dispatcher_reconnect_after_disconnect() -> None:
    calls = {"n": 0}

    approved_sent = {"done": False}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:

            async def fail_body():
                yield _sse_line({"type": "keepalive"})
                raise httpx.ReadError("connection reset")

            return httpx.Response(200, content=fail_body())

        async def ok_body():
            if not approved_sent["done"]:
                approved_sent["done"] = True
                yield _sse_line(
                    {
                        "type": "approved",
                        "login_request_id": "lr_1",
                        "agent_passport_jwt": "jwt.reconnect",
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
    received: list[str] = []

    async def capture(request_id: str, passport: str | None) -> None:
        if passport:
            received.append(passport)

    dispatcher = SiteEventDispatcher(client, [capture], backoff_base=0.01)
    asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.5), timeout=2.0)
    await dispatcher.stop()
    await client.aclose()

    assert received == ["jwt.reconnect"]
    assert calls["n"] >= 2


@pytest.mark.asyncio
async def test_dispatcher_sse_http_error_reconnects() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, content=b"down")

        async def body():
            yield _sse_line({"type": "keepalive"})

        return httpx.Response(200, content=body())

    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.01)
    task = asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.3), timeout=2.0)
    await dispatcher.stop()
    await client.aclose()

    assert calls["n"] >= 2
    assert task.done()


@pytest.mark.asyncio
async def test_dispatcher_error_frame_logged() -> None:
    client = _make_client(
        [
            _sse_line(
                {
                    "type": "error",
                    "code": "CHANNEL_DOWN",
                    "message": "redis unavailable",
                },
            ),
        ],
    )
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.01)
    task = asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.15), timeout=1.0)
    await dispatcher.stop()
    await client.aclose()
    assert task.done()


@pytest.mark.asyncio
async def test_dispatcher_stopped_mid_stream() -> None:
    client = _make_client([_sse_line({"type": "keepalive"})] * 50)
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.5)
    task = asyncio.create_task(dispatcher.run())
    await asyncio.sleep(0.05)
    await dispatcher.stop()
    await client.aclose()
    assert task.done()


@pytest.mark.asyncio
async def test_dispatcher_invalid_json_logs_and_continues() -> None:
    client = _make_client([b"data: not-json\n\n", _sse_line({"type": "keepalive"})])
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.01)
    task = asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.2), timeout=1.0)
    await dispatcher.stop()
    await client.aclose()
    assert task.done()


@pytest.mark.asyncio
async def test_dispatcher_cancelled_error_propagates() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:

            async def fail_body():
                yield _sse_line({"type": "keepalive"})
                raise httpx.ReadError("connection reset")

            return httpx.Response(200, content=fail_body())

        async def body():
            await asyncio.sleep(5.0)
            yield _sse_line({"type": "keepalive"})

        return httpx.Response(200, content=body())

    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.01)
    task = asyncio.create_task(dispatcher.run())
    await asyncio.sleep(0.15)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await client.aclose()


@pytest.mark.asyncio
async def test_dispatcher_stopped_after_stream_error_breaks() -> None:
    dispatcher_ref: list[SiteEventDispatcher] = []

    def handler(_: httpx.Request) -> httpx.Response:
        if dispatcher_ref:
            dispatcher_ref[0]._stopped = True

        async def fail_body():
            raise ValueError("stream boom")
            yield b""  # pragma: no cover

        return httpx.Response(200, content=fail_body())

    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.5)
    dispatcher_ref.append(dispatcher)
    task = asyncio.create_task(dispatcher.run())
    await asyncio.wait_for(asyncio.sleep(0.2), timeout=1.0)
    await client.aclose()
    assert task.done()


@pytest.mark.asyncio
async def test_dispatcher_stopped_mid_stream_returns() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        async def body():
            yield _sse_line({"type": "keepalive"})
            await asyncio.sleep(0.1)
            yield _sse_line({"type": "keepalive"})

        return httpx.Response(200, content=body())

    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.5)
    task = asyncio.create_task(dispatcher.run())
    await asyncio.sleep(0.05)
    dispatcher._stopped = True
    await asyncio.wait_for(asyncio.sleep(0.2), timeout=1.0)
    await client.aclose()
    assert task.done()


@pytest.mark.asyncio
async def test_dispatcher_dispatch_event_skips_missing_request_id() -> None:
    client = _make_client([])
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.5)
    called = False

    async def capture(_: str, __: str | None) -> None:
        nonlocal called
        called = True

    dispatcher._handlers.append(capture)
    await dispatcher._dispatch_event(
        SseDispatchEvent(kind=SseFrameKind.APPROVED, request_id=None, passport="jwt"),
    )
    await client.aclose()
    assert not called


@pytest.mark.asyncio
async def test_dispatcher_stop_cancels_run() -> None:
    client = _make_client([_sse_line({"type": "keepalive"})])
    dispatcher = SiteEventDispatcher(client, [], backoff_base=0.5)
    task = asyncio.create_task(dispatcher.run())
    dispatcher.attach_run_task(task)
    await dispatcher.stop()
    await client.aclose()
    assert task.done()
