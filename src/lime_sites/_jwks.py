from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import jwt
from jwt.algorithms import RSAAlgorithm

from lime_sites._client import LimeSiteClient
from lime_sites._errors import InvalidPassportError
from lime_sites._types import PassportVerificationResult

logger = logging.getLogger("lime")

_JWKS_SUFFIX = "/core/.well-known/jwks.json"
_LOGIN_AUD = "lime-site-login"
_BINDING_AUD = "lime-binding"
_LOGIN_MAX_TTL_SECONDS = 120
_BINDING_MAX_TTL_SECONDS = 60
_CLOCK_SKEW_LEEWAY_SECONDS = 30

_JWKS_CACHE_TTL_ENV = "LIME_JWKS_CACHE_TTL_SECONDS"
_JWKS_CACHE_TTL_DEFAULT_SECONDS = 300.0
_JWKS_CACHE_TTL_MAX_SECONDS = 86_400.0


@dataclass(frozen=True, slots=True)
class _CachedKey:
    key: Any
    fetched_at: float


_key_cache: dict[str, _CachedKey] = {}


async def verify_jwt(
    client: LimeSiteClient,
    jwt_token: str,
    *,
    expected_request_id: str | None = None,
) -> PassportVerificationResult:
    """Verify site-login agent passport JWT using cached JWKS."""
    expected_claim: tuple[str, str] | None = None
    if expected_request_id is not None:
        expected_claim = ("request_id", expected_request_id)
    return await _verify_jwt(
        client,
        jwt_token,
        expected_audience=_LOGIN_AUD,
        max_ttl_seconds=_LOGIN_MAX_TTL_SECONDS,
        expected_claim=expected_claim,
    )


async def verify_binding_jwt(
    client: LimeSiteClient,
    jwt_token: str,
) -> PassportVerificationResult:
    """Verify agent-binding passport JWT (``aud=lime-binding``).

    Cryptographic checks only (signature, audience, issuer, TTL, ``nbf``).
    Callers must match ``claims["binding_id"]`` to their pending row / user
    session themselves.
    """
    result = await _verify_jwt(
        client,
        jwt_token,
        expected_audience=_BINDING_AUD,
        max_ttl_seconds=_BINDING_MAX_TTL_SECONDS,
        expected_claim=None,
    )
    binding_id = result.claims.get("binding_id")
    if not isinstance(binding_id, str) or not binding_id.strip():
        raise InvalidPassportError("JWT missing binding_id claim")
    return result


async def _verify_jwt(
    client: LimeSiteClient,
    jwt_token: str,
    *,
    expected_audience: str,
    max_ttl_seconds: int,
    expected_claim: tuple[str, str] | None = None,
) -> PassportVerificationResult:
    try:
        header = jwt.get_unverified_header(jwt_token)
    except jwt.PyJWTError as exc:
        raise InvalidPassportError(f"JWT header is invalid: {exc}") from exc
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise InvalidPassportError("JWT header missing kid")

    key = await _resolve_key(client, kid)
    try:
        # verify_exp/iat/nbf off: we enforce expiry, TTL and nbf below with
        # platform rules. Disabling verify_iat/verify_nbf avoids false rejects
        # on small issuer/client clock skew (nbf gets a bounded leeway).
        claims = jwt.decode(
            jwt_token,
            key=key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
    except jwt.PyJWTError as exc:
        raise InvalidPassportError(f"JWT signature verification failed: {exc}") from exc

    if not isinstance(claims, dict):
        raise InvalidPassportError("JWT payload must be an object")

    aud = claims.get("aud")
    if aud != expected_audience:
        raise InvalidPassportError(
            f"Invalid audience: expected {expected_audience!r}, got {aud!r}",
        )

    issuer = claims.get("iss")
    if not isinstance(issuer, str) or not issuer.strip():
        raise InvalidPassportError("JWT missing iss claim")
    if _issuer_parts(issuer) != (*_origin_parts(client.base_url), ""):
        raise InvalidPassportError(
            f"Invalid issuer: expected base {client.base_url!r}, got {issuer!r}",
        )

    exp = claims.get("exp")
    iat = claims.get("iat")
    if not isinstance(exp, int | float) or not isinstance(iat, int | float):
        raise InvalidPassportError("JWT missing exp or iat")

    now = time.time()
    if exp <= now:
        raise InvalidPassportError("JWT has expired")

    if float(exp) - float(iat) > max_ttl_seconds:
        raise InvalidPassportError(
            f"JWT TTL exceeds platform maximum ({max_ttl_seconds}s)",
        )

    nbf = claims.get("nbf")
    if nbf is not None:
        if not isinstance(nbf, int | float):
            raise InvalidPassportError("JWT nbf claim must be a number")
        if float(nbf) > now + _CLOCK_SKEW_LEEWAY_SECONDS:
            raise InvalidPassportError("JWT is not yet valid (nbf in the future)")

    if expected_claim is not None:
        claim_name, expected_value = expected_claim
        claim_value = claims.get(claim_name)
        if str(claim_value) != expected_value:
            # verify_jwt is the only caller (expected_claim = request_id).
            raise InvalidPassportError(
                "JWT request_id claim does not match expected request",
            )

    normalized = _normalize_claims(claims)
    return PassportVerificationResult(valid=True, claims=normalized)


def clear_jwks_cache() -> None:
    """Clear in-memory JWKS cache (for tests)."""
    _key_cache.clear()


def _issuer_parts(value: str) -> tuple[str, str, str]:
    """Normalize an issuer value to (scheme, netloc, path) for equality.

    Scheme and host are case-insensitive; a trailing slash is not significant.
    """
    parts = urlsplit(value.strip())
    return (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"))


def _origin_parts(value: str) -> tuple[str, str]:
    """Origin (scheme, netloc) of a configured base URL, path ignored."""
    parts = urlsplit(value.strip())
    return (parts.scheme.lower(), parts.netloc.lower())


def _cache_ttl_seconds() -> float:
    """JWKS key-cache TTL in seconds (``LIME_JWKS_CACHE_TTL_SECONDS``).

    Defaults to 300s, clamps to ``[0, 86400]``. Invalid values fail closed:
    an unparsable TTL raises instead of silently keeping stale keys forever.
    """
    raw = os.environ.get(_JWKS_CACHE_TTL_ENV, "").strip()
    if not raw:
        return _JWKS_CACHE_TTL_DEFAULT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise InvalidPassportError(f"{_JWKS_CACHE_TTL_ENV} must be a number") from exc
    if value <= 0:
        return 0.0
    return min(value, _JWKS_CACHE_TTL_MAX_SECONDS)


def _jwks_path(base_url: str) -> str:
    """Return the JWKS spec path for a base URL.

    ``base_url`` may be either an origin (``https://lime.pics``) or the API root
    including ``/api/v1`` (``https://lime.pics/api/v1``). Real Core serves JWKS at
    ``/api/v1/core/.well-known/jwks.json``, so ensure the version prefix is present
    exactly once regardless of which ``base_url`` spelling the integrator used.
    """
    if base_url.rstrip("/").endswith("/api/v1"):
        return _JWKS_SUFFIX
    return f"/api/v1{_JWKS_SUFFIX}"


async def _resolve_key(client: LimeSiteClient, kid: str) -> Any:
    cached = _key_cache.get(kid)
    if cached is not None and (time.monotonic() - cached.fetched_at) < _cache_ttl_seconds():
        return cached.key

    await _refresh_jwks(client)
    cached = _key_cache.get(kid)
    if cached is None:
        await _refresh_jwks(client, force=True)
        cached = _key_cache.get(kid)
    if cached is None:
        raise InvalidPassportError(f"Unknown JWT kid: {kid}")
    return cached.key


async def _refresh_jwks(client: LimeSiteClient, *, force: bool = False) -> None:
    if force:
        _key_cache.clear()

    data = await client.fetch_spec_document(_jwks_path(client.base_url))
    keys = data.get("keys")
    if not isinstance(keys, list):
        raise InvalidPassportError("JWKS response missing keys array")

    now = time.monotonic()
    for jwk in keys:
        if not isinstance(jwk, dict):
            continue
        jwk_kid = jwk.get("kid")
        if not isinstance(jwk_kid, str) or not jwk_kid:
            continue
        try:
            _key_cache[jwk_kid] = _CachedKey(
                key=RSAAlgorithm.from_jwk(jwk),
                fetched_at=now,
            )
        except Exception as exc:
            logger.warning("Skipping invalid JWK kid=%s: %s", jwk_kid, exc)


def _normalize_claims(claims: dict[str, Any]) -> dict[str, Any]:
    out = dict(claims)
    sub = out.pop("sub", None)
    if sub is not None and "agent_id" not in out:
        out["agent_id"] = sub
    return out
