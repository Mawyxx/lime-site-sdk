from __future__ import annotations

import logging
import time
from typing import Any

import jwt
from jwt.algorithms import RSAAlgorithm

from lime_sites._client import LimeSiteClient
from lime_sites._errors import InvalidPassportError
from lime_sites._types import PassportVerificationResult

logger = logging.getLogger("lime")

_JWKS_PATH = "/core/.well-known/jwks.json"
_EXPECTED_AUD = "lime-site-login"
_MAX_TTL_SECONDS = 120

_key_cache: dict[str, Any] = {}


async def verify_jwt(
    client: LimeSiteClient,
    jwt_token: str,
    *,
    expected_request_id: str | None = None,
) -> PassportVerificationResult:
    """Verify agent passport JWT using cached JWKS."""
    header = jwt.get_unverified_header(jwt_token)
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise InvalidPassportError("JWT header missing kid")

    key = await _resolve_key(client, kid)
    try:
        claims = jwt.decode(
            jwt_token,
            key=key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_exp": False},
        )
    except jwt.PyJWTError as exc:
        raise InvalidPassportError(f"JWT signature verification failed: {exc}") from exc

    if not isinstance(claims, dict):
        raise InvalidPassportError("JWT payload must be an object")

    aud = claims.get("aud")
    if aud != _EXPECTED_AUD:
        raise InvalidPassportError(
            f"Invalid audience: expected {_EXPECTED_AUD!r}, got {aud!r}",
        )

    exp = claims.get("exp")
    iat = claims.get("iat")
    if not isinstance(exp, int | float) or not isinstance(iat, int | float):
        raise InvalidPassportError("JWT missing exp or iat")

    now = time.time()
    if exp <= now:
        raise InvalidPassportError("JWT has expired")

    if float(exp) - float(iat) > _MAX_TTL_SECONDS:
        raise InvalidPassportError(
            f"JWT TTL exceeds platform maximum ({_MAX_TTL_SECONDS}s)",
        )

    if expected_request_id is not None:
        claim_request_id = claims.get("request_id")
        if str(claim_request_id) != expected_request_id:
            raise InvalidPassportError(
                "JWT request_id claim does not match expected request",
            )

    normalized = _normalize_claims(claims)
    return PassportVerificationResult(valid=True, claims=normalized)


def clear_jwks_cache() -> None:
    """Clear in-memory JWKS cache (for tests)."""
    _key_cache.clear()


async def _resolve_key(client: LimeSiteClient, kid: str) -> Any:
    if kid in _key_cache:
        return _key_cache[kid]

    await _refresh_jwks(client)
    if kid not in _key_cache:
        await _refresh_jwks(client, force=True)
    if kid not in _key_cache:
        raise InvalidPassportError(f"Unknown JWT kid: {kid}")
    return _key_cache[kid]


async def _refresh_jwks(client: LimeSiteClient, *, force: bool = False) -> None:
    if force:
        _key_cache.clear()

    data = await client.get_public(_JWKS_PATH)
    keys = data.get("keys")
    if not isinstance(keys, list):
        raise InvalidPassportError("JWKS response missing keys array")

    for jwk in keys:
        if not isinstance(jwk, dict):
            continue
        jwk_kid = jwk.get("kid")
        if not isinstance(jwk_kid, str) or not jwk_kid:
            continue
        try:
            _key_cache[jwk_kid] = RSAAlgorithm.from_jwk(jwk)
        except Exception as exc:
            logger.warning("Skipping invalid JWK kid=%s: %s", jwk_kid, exc)


def _normalize_claims(claims: dict[str, Any]) -> dict[str, Any]:
    out = dict(claims)
    sub = out.pop("sub", None)
    if sub is not None and "agent_id" not in out:
        out["agent_id"] = sub
    return out
