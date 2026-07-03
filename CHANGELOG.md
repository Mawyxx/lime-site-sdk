# Changelog

All notable changes to this project will be documented in this file.

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
