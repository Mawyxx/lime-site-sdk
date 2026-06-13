"""Per-site SSE event dispatcher with infinite reconnect."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, MutableSequence

import httpx

from lime_sites._client import LimeSiteClient
from lime_sites._errors import ApiError
from lime_sites._sse import (
    _SSE_PATH,
    SseDispatchEvent,
    SseFrameKind,
    classify_sse_payload,
    iter_sse_data_payloads,
    parse_sse_json_payload,
)

logger = logging.getLogger("lime")

LoginHandler = Callable[[str, str | None], Awaitable[None]]

_SSE_READ_TIMEOUT = httpx.Timeout(connect=30.0, read=310.0, write=30.0, pool=30.0)
_MAX_BACKOFF_SEC = 8.0


class SiteEventDispatcher:
    """Background SSE consumer; dispatches site-login events to registered handlers."""

    def __init__(
        self,
        client: LimeSiteClient,
        handlers: MutableSequence[LoginHandler],
        *,
        backoff_base: float,
    ) -> None:
        self._client = client
        self._handlers = handlers
        self._backoff_base = backoff_base
        self._stopped = False
        self._run_task: asyncio.Task[None] | None = None

    def attach_run_task(self, task: asyncio.Task[None]) -> None:
        self._run_task = task

    async def run(self) -> None:
        self._run_task = asyncio.current_task()
        backoff = self._backoff_base
        while not self._stopped:
            try:
                await self._consume_stream()
                backoff = self._backoff_base
            except ApiError as exc:
                logger.error("SSE frame error: [%s] %s", exc.code, exc.message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("SSE connection dropped: %s", exc)

            if self._stopped:
                break

            logger.debug("SSE reconnect in %.2fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF_SEC)

    async def stop(self) -> None:
        self._stopped = True
        if self._run_task is not None and not self._run_task.done():
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass

    async def _consume_stream(self) -> None:
        buffer = ""
        async with self._client.stream(
            _SSE_PATH,
            timeout=_SSE_READ_TIMEOUT,
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                raise ApiError(
                    "SSE_HTTP_ERROR",
                    f"SSE stream failed (HTTP {response.status_code})",
                    http_status=response.status_code,
                    detail={"body": body.decode(errors="replace")[:200]},
                )

            async for chunk in response.aiter_text():
                if self._stopped:
                    return
                buffer, payloads = iter_sse_data_payloads(buffer, chunk)
                for payload_raw in payloads:
                    await self._dispatch_payload(payload_raw)

    async def _dispatch_payload(self, payload_raw: str) -> None:
        payload = parse_sse_json_payload(payload_raw)
        event = classify_sse_payload(payload)
        await self._dispatch_event(event)

    async def _dispatch_event(self, event: SseDispatchEvent) -> None:
        if event.kind == SseFrameKind.KEEPALIVE or event.kind == SseFrameKind.IGNORE:
            return

        if event.kind == SseFrameKind.ERROR:
            logger.error(
                "SSE error frame: [%s] %s",
                event.error_code,
                event.error_message,
            )
            return

        if event.request_id is None:
            return

        passport = event.passport if event.kind == SseFrameKind.APPROVED else None
        await self._invoke_handlers(event.request_id, passport)

    async def _invoke_handlers(self, request_id: str, passport: str | None) -> None:
        for handler in list(self._handlers):
            try:
                await handler(request_id, passport)
            except Exception:
                logger.exception(
                    "on_login handler failed for request_id=%s",
                    request_id,
                )
