# Changelog

All notable changes to this project will be documented in this file.

## [1.2.1] - 2026-07-18

### Fixed

- JWKS verify: disable PyJWT erify_iat so freshly issued passports are not rejected on small client/issuer clock skew (ImmatureSignatureError)
- Malformed JWT headers raise InvalidPassportError instead of raw DecodeError

[1.2.1]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.2.1

## [1.2.0] - 2026-07-18

### Added

- Agent Binding: LimeSite.create_binding_request(*, redirect_uri) -> BindingRequestResult
- Agent Binding: LimeSite.verify_binding_passport(jwt, *, expected_binding_id) (ud=lime-binding, TTL <= 60s)
- Export BindingRequestResult

### Changed

- Internal JWKS verifier parameterized for login (ud=lime-site-login, TTL <= 120s) vs binding

[1.2.0]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.2.0

## [1.1.0] - 2026-07-09

### Changed

- Fetch Core JWKS via etch_spec_document (RFC 7517 raw document, no LIME envelope)

[1.1.0]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.1.0


## [1.0.0] - 2026-06-09

### Breaking

- Removed `wait_for_login()` and `TimeoutError`. Site login events are delivered via registered `on_login` handlers instead of blocking per-request waits.
- `LimeSite()` must be constructed inside a running asyncio event loop (e.g. FastAPI lifespan). Synchronous construction raises `RuntimeError` with migration guidance.

### Added

- Auto-started `SiteEventDispatcher` — perpetual SSE listener on `GET /modules/agent-login/events` with exponential reconnect.
- `on_login(handler)` decorator / registrar: `async def handler(request_id: str, passport: str | None)`.
- `passport` is the agent JWT on `approved`; `None` on `expired`.

### Changed

- SSE parsing is internal; handlers receive all site-scoped events — map `request_id` to your user session in the handler.
- Documented: one `LimeSite` instance per site token per process.

[1.0.0]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.0.0

## [1.0.1] - 2026-06-14

### Changed

- README: full documentation for background `SiteEventDispatcher`, `on_login` handlers, migration from `wait_for_login`, FastAPI + asyncio examples.

[1.0.1]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.0.1

## [1.0.2] - 2026-07-03

### Changed

- README: SEO-focused rewrite — headless AI agent login, site passport JWT flow table, FastAPI + full-cycle examples with `lime-agents-sdk`, JWKS verification docs.
- PyPI `description` synced with README positioning.

[1.0.2]: https://github.com/Mawyxx/lime-site-sdk/releases/tag/v1.0.2
