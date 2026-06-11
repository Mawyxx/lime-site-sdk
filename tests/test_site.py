from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from lime_sites import LimeSite
from lime_sites._errors import AuthenticationError


def _envelope_ok(data: dict[str, Any]) -> bytes:
    return json.dumps({"ok": True, "data": data}).encode()


def _sse_line(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


@pytest.mark.asyncio
async def test_create_login_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Site-Token"] == "st_secret"
        assert json.loads(request.content) == {}
        return httpx.Response(
            201,
            content=_envelope_ok(
                {
                    "login_request_id": "lr_test",
                    "status": "PENDING",
                    "expires_at": "2026-06-10T12:00:00+00:00",
                },
            ),
        )

    site = LimeSite(
        site_token="st_secret",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await site.create_login_request()
    await site.aclose()

    assert result.request_id == "lr_test"
    assert result.status == "PENDING"
    assert result.expires_at.isoformat().startswith("2026-06-10")


@pytest.mark.asyncio
async def test_full_mock_flow() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk.update({"kid": "site-flow-kid", "alg": "RS256", "use": "sig"})
    now = int(time.time())
    passport = jwt.encode(
        {
            "sub": "agent_1",
            "aud": "lime-site-login",
            "iat": now,
            "exp": now + 60,
            "request_id": "lr_flow",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "site-flow-kid"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url.path)
        if path.endswith("/modules/agent-login/requests") and request.method == "POST":
            return httpx.Response(
                201,
                content=_envelope_ok(
                    {
                        "login_request_id": "lr_flow",
                        "status": "PENDING",
                        "expires_at": "2026-06-10T12:00:00+00:00",
                    },
                ),
            )
        if path.endswith("/modules/agent-login/events"):
            async def body():
                yield _sse_line(
                    {
                        "type": "approved",
                        "login_request_id": "lr_flow",
                        "status": "approved",
                        "agent_passport_jwt": passport,
                    },
                )

            return httpx.Response(200, content=body())
        if path.endswith("/jwks.json"):
            return httpx.Response(200, content=_envelope_ok({"keys": [jwk]}))
        return httpx.Response(404)

    site = LimeSite(
        site_token="st_secret",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    req = await site.create_login_request()
    login = await site.wait_for_login(req.request_id, timeout=5.0)
    verified = await site.verify_passport(
        login.agent_passport_jwt,
        expected_request_id=req.request_id,
    )
    await site.aclose()

    assert login.request_id == "lr_flow"
    assert verified.valid is True
    assert verified.claims["agent_id"] == "agent_1"


def test_missing_token_raises() -> None:
    old = os.environ.pop("LIME_SITE_TOKEN", None)
    try:
        with pytest.raises(AuthenticationError, match="Site token is required"):
            LimeSite()
    finally:
        if old is not None:
            os.environ["LIME_SITE_TOKEN"] = old


def test_reads_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIME_SITE_TOKEN", "st_from_env")
    site = LimeSite()
    assert site._client._site_token == "st_from_env"  # noqa: SLF001


def test_reads_base_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIME_SITE_TOKEN", "st_x")
    monkeypatch.setenv("LIME_API_BASE", "http://custom/api/v1")
    site = LimeSite()
    assert site._client._base_url == "http://custom/api/v1"  # noqa: SLF001


@pytest.mark.asyncio
async def test_context_manager() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            content=_envelope_ok(
                {
                    "login_request_id": "lr_ctx",
                    "status": "PENDING",
                    "expires_at": "2026-06-10T12:00:00+00:00",
                },
            ),
        )

    transport = httpx.MockTransport(handler)
    async with LimeSite(
        site_token="st_x",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=transport),
    ) as site:
        req = await site.create_login_request()
    assert req.request_id == "lr_ctx"
