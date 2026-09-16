# Changelog

All notable changes to this project will be documented in this file.

## [2.0.3] - 2026-09-16

### Fixed

- JWKS resolution works with either `base_url` spelling (origin `https://lime.pics`
  or API root including `/api/v1`). Real Core serves JWKS at
  `/api/v1/core/.well-known/jwks.json`; previously an origin-style `base_url`
  produced `/core/.well-known/jwks.json`, which hung against production until
  timeout. The version prefix is now applied exactly once, and `LimeSite` default
  behavior (`https://lime.pics/api/v1`) is unchanged.

### Docs / DX

- README + binding example: callback is `?binding_code=` &#8594; `POST /bindings/exchange` &#8594; `verify_binding_passport` (never JWT in the URL).
- Canonical docs table points at lime.pics / GitHub (not RTD as primary).

## [2.0.2] - 2026-09-11

### Changed

- Test JWT fixtures no longer include retired `agent_reputation` / `owner_kyc_level`
  claims (platform passport_version=5 / ADR 0105). Verification APIs unchanged.

## [2.0.1] - 2026-09-11

### Changed

- Passport claim docs/fixtures: drop retired `user_kyc_level` / `owner_kyc_level`;
  document `passport_version=4`.

## [2.0.0] - 2026-07-19

### Breaking

- `LimeSite.verify_binding_passport(jwt)` no longer accepts `expected_binding_id`.
  The SDK performs cryptographic verification only (RS256/JWKS, `aud=lime-binding`,
  TTL ≤ 60s, non-empty `binding_id` claim). Matching `claims["binding_id"]` to your
  pending row / `user_id` is integrator business logic.

### Changed

- `verify_binding_jwt` requires a non-empty `binding_id` claim after decode; it does
  not compare the claim to a caller-supplied value.

[2.0.0]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v2.0.0

## [1.2.1] - 2026-07-18

### Fixed

- JWKS verify: disable PyJWT `verify_iat` so freshly issued passports are not rejected
  on small client/issuer clock skew (ImmatureSignatureError)
- Malformed JWT headers raise InvalidPassportError instead of raw DecodeError

[1.2.1]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.2.1

## [1.2.0] - 2026-07-18

### Added

- Agent Binding: LimeSite.create_binding_request(*, redirect_uri) -> BindingRequestResult
- Agent Binding: LimeSite.verify_binding_passport(jwt, *, expected_binding_id)
  (`aud=lime-binding`, TTL <= 60s)
- Export BindingRequestResult

### Changed

- Internal JWKS verifier parameterized for login (`aud=lime-site-login`, TTL <= 120s)
  vs binding

[1.2.0]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.2.0

## [1.1.0] - 2026-07-09

### Changed

- Fetch Core JWKS via `fetch_spec_document` (RFC 7517 raw document, no LIME envelope)

[1.1.0]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.1.0

## [1.0.0] - 2026-06-09

### Breaking

- Removed `wait_for_login()` and `TimeoutError`. Site login events are delivered via
  registered `on_login` handlers instead of blocking per-request waits.
- `LimeSite()` must be constructed inside a running asyncio event loop (e.g. FastAPI
  lifespan). Synchronous construction raises `RuntimeError` with migration guidance.

### Added

- Auto-started `SiteEventDispatcher` — perpetual SSE listener on
  `GET /modules/agent-login/events` with exponential reconnect.
- `on_login(handler)` decorator / registrar:
  `async def handler(request_id: str, passport: str | None)`.
- `passport` is the agent JWT on `approved`; `None` on `expired`.

### Changed

- SSE parsing is internal; handlers receive all site-scoped events — map `request_id`
  to your user session in the handler.
- Documented: one `LimeSite` instance per site token per process.

[1.0.0]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.0.0

## [1.0.1] - 2026-06-14

### Changed

- README: full documentation for background `SiteEventDispatcher`, `on_login` handlers,
  migration from `wait_for_login`, FastAPI + asyncio examples.

[1.0.1]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.0.1

## [1.0.2] - 2026-07-03

### Changed

- README: SEO-focused rewrite — headless AI agent login, site passport JWT flow table,
  FastAPI + full-cycle examples with `lime-agents-sdk`, JWKS verification docs.
- PyPI `description` synced with README positioning.

[1.0.2]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.0.2