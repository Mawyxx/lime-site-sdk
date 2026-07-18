from __future__ import annotations

import inspect
import json
import time
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from lime_sites import BindingRequestResult, LimeSite
from lime_sites._client import LimeSiteClient
from lime_sites._errors import ApiError, AuthenticationError, InvalidPassportError
from lime_sites._jwks import clear_jwks_cache, verify_binding_jwt
from lime_sites._types import BindingRequestResult as BindingRequestResultType


def _envelope_ok(data: dict[str, Any]) -> bytes:
    return json.dumps({"ok": True, "data": data}).encode()


def _envelope_err(code: str, message: str, *, status: int = 400) -> bytes:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}},
    ).encode()


def _jwks_ok(jwks_keys: list[dict[str, Any]]) -> bytes:
    return json.dumps({"keys": jwks_keys}).encode()


@pytest.fixture
def rsa_keys() -> tuple[Any, dict[str, Any], str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = "binding-kid-1"
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return private_key, jwk, "binding-kid-1"


def _make_client(jwks_keys: list[dict[str, Any]]) -> LimeSiteClient:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_jwks_ok(jwks_keys))

    return LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _sign_binding(
    private_key: Any,
    kid: str,
    *,
    aud: str = "lime-binding",
    binding_id: str = "br_test",
    ttl: int = 60,
    sub: str = "agent_99",
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": aud,
            "iat": now,
            "exp": now + ttl,
            "binding_id": binding_id,
            "user_id": "user_1",
            "user_kyc_level": 1,
            "passport_version": "3",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_jwks_cache()
    yield
    clear_jwks_cache()


def test_binding_request_result_from_api() -> None:
    result = BindingRequestResultType.from_api(
        {
            "binding_id": "br_1",
            "connect_url": "https://lime.pics/connect/?binding_id=br_1",
            "status": "PENDING",
            "expires_at": "2026-06-10T12:00:00Z",
        },
    )
    assert result.binding_id == "br_1"
    assert result.connect_url.endswith("binding_id=br_1")
    assert result.status == "PENDING"
    assert result.expires_at.year == 2026


@pytest.mark.asyncio
async def test_create_binding_request_wire() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = str(request.url.path)
        seen["token"] = request.headers.get("X-Site-Token")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            content=_envelope_ok(
                {
                    "binding_id": "br_created",
                    "connect_url": "https://lime.pics/connect/?binding_id=br_created",
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
    result = await site.create_binding_request(
        redirect_uri="https://app.example/callback",
    )
    await site.aclose()

    assert seen["method"] == "POST"
    assert seen["path"].endswith("/modules/bindings/requests")
    assert seen["token"] == "st_secret"
    assert seen["body"] == {"redirect_uri": "https://app.example/callback"}
    assert isinstance(result, BindingRequestResult)
    assert result.binding_id == "br_created"
    assert result.connect_url == "https://lime.pics/connect/?binding_id=br_created"
    assert result.status == "PENDING"


@pytest.mark.asyncio
async def test_create_binding_request_401() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            content=_envelope_err("SITE_TOKEN_INVALID", "bad token", status=401),
        )

    site = LimeSite(
        site_token="st_bad",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(AuthenticationError):
        await site.create_binding_request(redirect_uri="https://app.example/cb")
    await site.aclose()


@pytest.mark.asyncio
async def test_create_binding_request_400() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            content=_envelope_err("VALIDATION_ERROR", "bad redirect"),
        )

    site = LimeSite(
        site_token="st_x",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ApiError):
        await site.create_binding_request(redirect_uri="not-a-url")
    await site.aclose()


@pytest.mark.asyncio
async def test_verify_binding_passport_success(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    passport = _sign_binding(private_key, kid, binding_id="br_ok")

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url.path).endswith("/jwks.json"):
            return httpx.Response(200, content=_jwks_ok([jwk]))
        return httpx.Response(404)

    site = LimeSite(
        site_token="st_x",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await site.verify_binding_passport(
        passport,
        expected_binding_id="br_ok",
    )
    await site.aclose()

    assert result.valid is True
    assert result.claims["agent_id"] == "agent_99"
    assert result.claims["binding_id"] == "br_ok"
    assert result.claims["user_id"] == "user_1"


@pytest.mark.asyncio
async def test_verify_binding_wrong_aud(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_binding(private_key, kid, aud="lime-site-login")
    with pytest.raises(InvalidPassportError, match="audience"):
        await verify_binding_jwt(client, token, expected_binding_id="br_test")
    await client.aclose()


@pytest.mark.asyncio
async def test_verify_binding_wrong_binding_id(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_binding(private_key, kid, binding_id="br_a")
    with pytest.raises(InvalidPassportError, match="binding_id"):
        await verify_binding_jwt(client, token, expected_binding_id="br_b")
    await client.aclose()


@pytest.mark.asyncio
async def test_verify_binding_missing_binding_id_claim(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "agent_1",
            "aud": "lime-binding",
            "iat": now,
            "exp": now + 60,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    with pytest.raises(InvalidPassportError, match="binding_id"):
        await verify_binding_jwt(client, token, expected_binding_id="br_x")
    await client.aclose()


@pytest.mark.asyncio
async def test_verify_binding_expired(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "agent_1",
            "aud": "lime-binding",
            "iat": now - 120,
            "exp": now - 60,
            "binding_id": "br_x",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    with pytest.raises(InvalidPassportError, match="expired"):
        await verify_binding_jwt(client, token, expected_binding_id="br_x")
    await client.aclose()


@pytest.mark.asyncio
async def test_verify_binding_ttl_too_long(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_binding(private_key, kid, ttl=61)
    with pytest.raises(InvalidPassportError, match="TTL"):
        await verify_binding_jwt(client, token, expected_binding_id="br_test")
    await client.aclose()


@pytest.mark.asyncio
async def test_verify_binding_bad_signature(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = _make_client([jwk])
    token = _sign_binding(other, kid)
    with pytest.raises(InvalidPassportError, match="signature"):
        await verify_binding_jwt(client, token, expected_binding_id="br_test")
    await client.aclose()


@pytest.mark.asyncio
async def test_verify_binding_empty_expected_id(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_binding(private_key, kid)
    with pytest.raises(InvalidPassportError, match="expected_binding_id"):
        await verify_binding_jwt(client, token, expected_binding_id="  ")
    await client.aclose()


def test_verify_binding_passport_requires_keyword() -> None:
    sig = inspect.signature(LimeSite.verify_binding_passport)
    params = list(sig.parameters.values())
    # self, jwt, *, expected_binding_id
    assert params[2].kind is inspect.Parameter.KEYWORD_ONLY
    assert params[2].name == "expected_binding_id"
    assert params[2].default is inspect.Parameter.empty


@pytest.mark.asyncio
async def test_verify_binding_passport_missing_arg_typeerror() -> None:
    site = LimeSite(
        site_token="st_x",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(404)),
        ),
    )
    with pytest.raises(TypeError):
        await site.verify_binding_passport("jwt.token")  # type: ignore[call-arg]
    await site.aclose()


@pytest.mark.asyncio
async def test_login_jwt_rejected_by_binding_verify(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    now = int(time.time())
    login_token = jwt.encode(
        {
            "sub": "agent_1",
            "aud": "lime-site-login",
            "iat": now,
            "exp": now + 60,
            "request_id": "lr_1",
            "binding_id": "br_spoof",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    with pytest.raises(InvalidPassportError, match="audience"):
        await verify_binding_jwt(client, login_token, expected_binding_id="br_spoof")
    await client.aclose()
