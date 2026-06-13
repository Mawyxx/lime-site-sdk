# LIME Sites SDK

[![PyPI version](https://img.shields.io/pypi/v/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-site-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-site-sdk/actions/workflows/ci.yml)

Official Python SDK for [LIME](https://lime.pics) site backends. Async-first client: create login requests, receive agent approval over a perpetual SSE dispatcher, verify JWT passports via JWKS.

> **Repository:** [lime-site-sdk](https://github.com/Mawyxx/lime-site-sdk) · **PyPI:** `lime-sites-sdk` · **Import:** `from lime_sites import LimeSite`

Pair with [lime-agents-sdk](https://github.com/Mawyxx/lime-agents-sdk) on the agent worker side.

## Installation

```bash
pip install lime-sites-sdk
```

Install the latest commit from GitHub:

```bash
pip install git+https://github.com/Mawyxx/lime-site-sdk.git
```

**Requirements:** Python 3.10+

## Quick start (FastAPI)

`LimeSite` starts an SSE event dispatcher automatically when constructed inside a running event loop. Register `on_login` handlers to receive `approved` / `expired` events for any login request on this site.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from lime_sites import LimeSite

site: LimeSite


@asynccontextmanager
async def lifespan(app: FastAPI):
    global site
    site = LimeSite()  # LIME_SITE_TOKEN; loop running → listener starts

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        if passport is None:
            return  # expired — map request_id → session and clear pending state
        verified = await site.verify_passport(passport, expected_request_id=request_id)
        # route request_id → user session using verified.claims

    yield
    await site.aclose()


app = FastAPI(lifespan=lifespan)


@app.post("/login/start")
async def start_login() -> dict[str, str]:
    req = await site.create_login_request()
  # pass req.request_id to agent worker (lime-agents-sdk approve)
    return {"request_id": req.request_id}
```

## Handler contract

| Event | `passport` | Action |
|-------|------------|--------|
| `approved` | agent JWT string | `verify_passport(passport, expected_request_id=request_id)` |
| `expired` | `None` | clear pending login for `request_id` |

Handlers run sequentially for each event. Keep them fast; offload heavy work to a background queue.

## Production deployment

- Create **one** `LimeSite` per site token per process at startup (not per HTTP request).
- Construct only inside an async context (`lifespan`, `asyncio.run`, etc.).
- Optionally pass a shared `httpx.AsyncClient` via `http_client` for connection pooling.
- nginx `proxy_read_timeout` on `GET /modules/agent-login/events` should be **≥ 310s** (production default). The SDK uses a dedicated 310s SSE read timeout and reconnects on drops.

```python
import httpx
from lime_sites import LimeSite

http_client = httpx.AsyncClient(timeout=30.0)
site = LimeSite(http_client=http_client)

@site.on_login
async def on_login(request_id: str, passport: str | None) -> None:
    ...
```

Call `site.aclose()` only on process shutdown.

## Authentication

Site HTTP calls use the `X-Site-Token` header.

**Resolution order:**

1. Constructor argument `site_token="st_..."`
2. Environment variable `LIME_SITE_TOKEN`

If neither is set, construction raises `AuthenticationError`.

## Configuration

| Variable | Purpose |
|----------|---------|
| `LIME_SITE_TOKEN` | Site integration token (required) |
| `LIME_API_BASE` | API root including `/api/v1` (default `https://lime.pics/api/v1`) |

## API reference

### `LimeSite`

Async client for site-backend operations.

#### Constructor

All arguments are keyword-only. Must be called inside a running asyncio loop.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `site_token` | `str \| None` | `None` | Site secret. Falls back to `LIME_SITE_TOKEN`. |
| `base_url` | `str \| None` | `None` | API root. Falls back to `LIME_API_BASE`, then production default. |
| `timeout` | `float` | `30.0` | Per HTTP request timeout (seconds). |
| `max_retries` | `int` | `3` | Retries on transient 5xx / transport errors. |
| `sse_backoff_base` | `float` | `0.5` | Initial SSE reconnect backoff (seconds). |
| `http_client` | `httpx.AsyncClient \| None` | `None` | Inject for tests. |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `on_login(handler)` | `handler` | Register async handler; usable as `@site.on_login` decorator |
| `create_login_request()` | `LoginRequestResult` | `POST /modules/agent-login/requests` |
| `verify_passport(jwt, *, expected_request_id=None)` | `PassportVerificationResult` | JWKS RS256 verify |
| `aclose()` | `None` | Stop dispatcher and close owned HTTP client |

Supports `async with LimeSite(...) as site:` (still requires running loop at enter).

### Types

| Type | Fields |
|------|--------|
| `LoginRequestResult` | `request_id`, `status`, `expires_at` |
| `PassportVerificationResult` | `valid`, `claims` |

### Errors

| Exception | When |
|-----------|------|
| `AuthenticationError` | Missing/invalid site token |
| `RequestExpiredError` | JWT / request binding expired (verify path) |
| `InvalidPassportError` | JWT verify failure |
| `RateLimitError` | HTTP 429 |
| `ApiError` | Other API errors |
| `LimeError` | Base class |

## Integration pattern

1. At startup: `site = LimeSite()` + `@site.on_login` handler.
2. User login flow: `req = await site.create_login_request()`; store `request_id` in session.
3. Deliver `request_id` to agent worker (`lime-agents-sdk` `approve(request_id)`).
4. Dispatcher invokes handler with JWT → `verify_passport` → create local session.
5. On `expired`, handler receives `passport=None` for that `request_id`.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
mypy src/lime_sites
pytest --cov=lime_sites --cov-fail-under=100
```

Live integration (requires tokens):

```bash
pip install lime-agents-sdk lime-sites-sdk
LIME_INTEGRATION=1 pytest tests/integration -v
```

**Full cycle (both SDKs):** `tests/integration/test_full_cycle_both_sdks.py` — site create → agent approve → SSE passport → JWKS verify → agent profile.

Run from the production VPS via the LIME monorepo:

```bash
python scripts/_run_both_sdks_integration_remote.py
```

## License

MIT — see [LICENSE](LICENSE).
