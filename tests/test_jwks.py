from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import patch

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from lime_sites._client import LimeSiteClient
from lime_sites._errors import InvalidPassportError
from lime_sites._jwks import clear_jwks_cache, verify_jwt


def _jwks_ok(jwks_keys: list[dict[str, Any]]) -> bytes:
    return json.dumps({"keys": jwks_keys}).encode()


@pytest.fixture
def rsa_keys() -> tuple[Any, dict[str, Any], str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = "test-kid-1"
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return private_key, jwk, "test-kid-1"


def _make_client(
    jwks_keys: list[dict[str, Any]],
    *,
    refresh_count: list[int] | None = None,
) -> LimeSiteClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if refresh_count is not None:
            refresh_count[0] += 1
        return httpx.Response(200, content=_jwks_ok(jwks_keys))

    return LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _sign_token(
    private_key: Any,
    kid: str,
    *,
    aud: str = "lime-site-login",
    request_id: str = "lr_test",
    ttl: int = 60,
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "agent_123",
            "aud": aud,
            "iat": now,
            "exp": now + ttl,
            "request_id": request_id,
            "owner_id": "owner_1",
            "owner_kyc_level": 1,
            "agent_reputation": 10,
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


@pytest.mark.asyncio
async def test_verify_valid_jwt(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_token(private_key, kid)

    result = await verify_jwt(client, token, expected_request_id="lr_test")
    assert result.valid is True
    assert result.claims["agent_id"] == "agent_123"
    assert result.claims["request_id"] == "lr_test"
    await client.aclose()


@pytest.mark.asyncio
async def test_jwks_cache_avoids_refetch(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    refresh_count = [0]
    client = _make_client([jwk], refresh_count=refresh_count)
    token = _sign_token(private_key, kid)

    await verify_jwt(client, token)
    await verify_jwt(client, token)
    assert refresh_count[0] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_unknown_kid_raises_when_not_in_jwks(rsa_keys) -> None:
    private_key, jwk, _kid = rsa_keys
    token = jwt.encode(
        {
            "sub": "a",
            "aud": "lime-site-login",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "absent-kid"},
    )
    client = _make_client([jwk])
    with pytest.raises(InvalidPassportError, match="Unknown JWT kid"):
        await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_kid_miss_triggers_jwks_refresh(rsa_keys) -> None:
    private_key, jwk, _kid = rsa_keys
    jwk_copy = dict(jwk)
    jwk_copy["kid"] = "late-kid"
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        keys = [jwk] if calls["n"] == 1 else [jwk_copy]
        return httpx.Response(200, content=_jwks_ok(keys))

    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    token = jwt.encode(
        {
            "sub": "a",
            "aud": "lime-site-login",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "late-kid"},
    )
    clear_jwks_cache()
    result = await verify_jwt(client, token)
    assert result.valid is True
    assert calls["n"] >= 2
    await client.aclose()


@pytest.mark.asyncio
async def test_bad_signature(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = _make_client([jwk])
    token = _sign_token(other_key, kid)

    with pytest.raises(InvalidPassportError, match="signature"):
        await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_wrong_audience(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_token(private_key, kid, aud="wrong-aud")

    with pytest.raises(InvalidPassportError, match="audience"):
        await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_expired_jwt(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "agent_123",
            "aud": "lime-site-login",
            "iat": now - 120,
            "exp": now - 60,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )

    with pytest.raises(InvalidPassportError, match="expired"):
        await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_ttl_too_long(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_token(private_key, kid, ttl=200)

    with pytest.raises(InvalidPassportError, match="TTL"):
        await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_request_id_mismatch(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_token(private_key, kid, request_id="lr_a")

    with pytest.raises(InvalidPassportError, match="request_id"):
        await verify_jwt(client, token, expected_request_id="lr_b")
    await client.aclose()


@pytest.mark.asyncio
async def test_missing_kid_header(rsa_keys) -> None:
    private_key, jwk, _kid = rsa_keys
    client = _make_client([jwk])
    now = int(time.time())
    token = jwt.encode(
        {"sub": "a", "aud": "lime-site-login", "iat": now, "exp": now + 60},
        private_key,
        algorithm="RS256",
    )

    with pytest.raises(InvalidPassportError, match="kid"):
        await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_jwks_missing_keys_array() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"keys": "bad"}).encode())

    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    token = jwt.encode(
        {"sub": "a", "aud": "lime-site-login", "iat": now, "exp": now + 60},
        private_key,
        algorithm="RS256",
        headers={"kid": "any"},
    )

    with pytest.raises(InvalidPassportError, match="keys array"):
        await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_missing_exp_or_iat(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = jwt.encode(
        {"sub": "a", "aud": "lime-site-login"},
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )

    with pytest.raises(InvalidPassportError, match="exp or iat"):
        await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_non_dict_claims_raises(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    token = _sign_token(private_key, kid)

    with patch("lime_sites._jwks.jwt.decode", return_value="not-a-dict"):
        with pytest.raises(InvalidPassportError, match="payload must be an object"):
            await verify_jwt(client, token)
    await client.aclose()


@pytest.mark.asyncio
async def test_skips_malformed_jwk_entries(rsa_keys) -> None:
    private_key, jwk, kid = rsa_keys
    keys_payload = [
        "not-a-dict",
        {"kid": ""},
        {"kid": "bad-key", "kty": "RSA", "n": "!!!", "e": "AQAB"},
        jwk,
    ]
    client = _make_client(keys_payload)
    token = _sign_token(private_key, kid)
    result = await verify_jwt(client, token)
    assert result.valid is True
    await client.aclose()

@pytest.mark.asyncio
async def test_iat_slightly_in_future_accepted(rsa_keys) -> None:
    """Issuer clock ahead of verifier must not reject a fresh passport."""
    private_key, jwk, kid = rsa_keys
    client = _make_client([jwk])
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "agent_123",
            "aud": "lime-site-login",
            "iat": now + 5,
            "exp": now + 65,
            "request_id": "lr_skew",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    result = await verify_jwt(client, token, expected_request_id="lr_skew")
    assert result.valid is True
    await client.aclose()


@pytest.mark.asyncio
async def test_malformed_jwt_header_raises_invalid_passport() -> None:
    client = LimeSiteClient(
        site_token="st_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(404)),
        ),
    )
    with pytest.raises(InvalidPassportError, match="header"):
        await verify_jwt(client, "not-a-jwt")
    await client.aclose()

