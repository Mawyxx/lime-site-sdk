from __future__ import annotations

import asyncio
import os
from types import TracebackType

import httpx

from lime_sites._client import LimeSiteClient
from lime_sites._dispatcher import LoginHandler, SiteEventDispatcher
from lime_sites._errors import AuthenticationError
from lime_sites._jwks import verify_jwt
from lime_sites._types import LoginRequestResult, PassportVerificationResult

_DEFAULT_BASE_URL = "https://lime.pics/api/v1"
_LOOP_REQUIRED_MSG = (
    "LimeSite must be constructed inside a running asyncio event loop "
    "(e.g. FastAPI lifespan or asyncio.run). Register on_login handlers for SSE delivery."
)


class LimeSite:
    """Async client for LIME site backends with auto-started SSE event dispatcher."""

    def __init__(
        self,
        *,
        site_token: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        sse_backoff_base: float = 0.5,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved_token = (site_token or os.getenv("LIME_SITE_TOKEN") or "").strip()
        if not resolved_token:
            raise AuthenticationError(
                "Site token is required. Pass site_token= or set LIME_SITE_TOKEN.",
            )

        resolved_base = (
            base_url or os.getenv("LIME_API_BASE") or _DEFAULT_BASE_URL
        ).rstrip("/")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeError(_LOOP_REQUIRED_MSG) from exc

        self._sse_backoff_base = sse_backoff_base
        self._handlers: list[LoginHandler] = []
        self._client = LimeSiteClient(
            site_token=resolved_token,
            base_url=resolved_base,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )
        self._dispatcher = SiteEventDispatcher(
            self._client,
            self._handlers,
            backoff_base=sse_backoff_base,
        )
        self._dispatcher_task = loop.create_task(
            self._dispatcher.run(),
            name="lime_sites_event_dispatcher",
        )
        self._dispatcher.attach_run_task(self._dispatcher_task)

    async def __aenter__(self) -> LimeSite:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def on_login(self, handler: LoginHandler) -> LoginHandler:
        """Register a handler for site-login SSE events (approved or expired)."""
        self._handlers.append(handler)
        return handler

    async def aclose(self) -> None:
        await self._dispatcher.stop()
        await self._client.aclose()

    async def create_login_request(self) -> LoginRequestResult:
        """Create a PENDING site-login request."""
        data = await self._client.post("/modules/agent-login/requests", {})
        return LoginRequestResult.from_api(data)

    async def verify_passport(
        self,
        jwt: str,
        *,
        expected_request_id: str | None = None,
    ) -> PassportVerificationResult:
        """Verify agent passport JWT via JWKS."""
        return await verify_jwt(
            self._client,
            jwt,
            expected_request_id=expected_request_id,
        )
