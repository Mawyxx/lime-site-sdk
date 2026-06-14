# LIME Sites SDK

[![PyPI version](https://img.shields.io/pypi/v/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-site-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-site-sdk/actions/workflows/ci.yml)

Official Python SDK for [LIME](https://lime.pics) **site backends**. Async-first: create login requests, receive agent passports over a **background SSE dispatcher**, verify JWTs via JWKS.

> **Repository:** [lime-site-sdk](https://github.com/Mawyxx/lime-site-sdk) · **PyPI:** `lime-sites-sdk` · **Import:** `from lime_sites import LimeSite`

Pair with [lime-agents-sdk](https://github.com/Mawyxx/lime-agents-sdk) on the agent worker side.

## Installation

```bash
pip install lime-sites-sdk
```

Latest from GitHub (if PyPI lags):

```bash
pip install "git+https://github.com/Mawyxx/lime-site-sdk.git@v1.0.1"
```

**Requirements:** Python 3.10+

## Background SSE dispatcher (v1.0+)

**v1.0 removed `wait_for_login()`.** Instead, `LimeSite` starts an internal **`SiteEventDispatcher`** when you construct it inside a **running asyncio loop**:

1. Opens perpetual `GET /modules/agent-login/events` (`text/event-stream`, `X-Site-Token`).
2. Parses SSE frames (`approved`, `expired`, `keepalive`) with automatic reconnect and exponential backoff.
3. On each terminal event, calls your registered **`on_login`** handlers: `(request_id, passport | None)`.
4. Stops on `await site.aclose()` (process shutdown).

You map `request_id` → user session in the handler. The dispatcher delivers **all** login events for this site token — not one blocking wait per HTTP request.

```
┌─────────────────────────────────────────────────────────────┐
│  Your site backend process (one LimeSite per site token)    │
│                                                             │
│  LimeSite()  ──► SiteEventDispatcher (background task)      │
│       │              │                                      │
│       │              └──► GET /agent-login/events (loop)    │
│       │                      │ approved / expired           │
│       ▼                      ▼                              │
│  create_login_request()   @site.on_login handlers           │
│       │                      │                              │
│       └── request_id ───────► verify_passport → session     │
└─────────────────────────────────────────────────────────────┘
```

**Rules:**

| Rule | Why |
|------|-----|
| **One `LimeSite` per site token per process** | One SSE connection per site |
| Construct only inside running loop (`lifespan`, `asyncio.run`) | Dispatcher is `asyncio.create_task(...)` |
| Handlers must be **fast** | They run sequentially on the dispatcher thread |
| `passport=None` means **expired** | Clear pending login for that `request_id` |

**Not public API:** no `start()` / `stop()` — lifecycle is `LimeSite()` + `aclose()`.

### Migration from 0.1.0 (`wait_for_login`)

| 0.1.0 | 1.0+ |
|-------|------|
| `site = LimeSite()` anywhere | `site = LimeSite()` inside running event loop |
| `login = await site.wait_for_login(req.request_id)` | `@site.on_login` receives JWT when agent approves |
| Blocking wait per request | Map `request_id` in handler to your session store |
| `TimeoutError` | Use your own timeout on pending session state |

## Quick start (FastAPI)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from lime_sites import LimeSite

site: LimeSite


@asynccontextmanager
async def lifespan(app: FastAPI):
    global site
    site = LimeSite()  # LIME_SITE_TOKEN; loop running → dispatcher starts

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        if passport is None:
            pending_logins.pop(request_id, None)  # expired
            return
        verified = await site.verify_passport(
            passport,
            expected_request_id=request_id,
        )
        pending_logins[request_id] = verified.claims  # or issue session cookie

    yield
    await site.aclose()


app = FastAPI(lifespan=lifespan)

# In-memory map: request_id → claims (use Redis/DB in production)
pending_logins: dict[str, object] = {}


@app.post("/login/start")
async def start_login() -> dict[str, str]:
    req = await site.create_login_request()
    # Pass req.request_id to agent worker (lime-agents-sdk approve + PoW)
    return {"request_id": req.request_id}
```

## Minimal example (`asyncio.run`)

```python
import asyncio
from lime_sites import LimeSite

pending: dict[str, str | None] = {}


async def main() -> None:
    site = LimeSite()  # must be inside async main (running loop)

    @site.on_login
    async def on_login(request_id: str, passport: str | None) -> None:
        pending[request_id] = passport

    req = await site.create_login_request()
    # hand req.request_id to agent; after approve, pending[req.request_id] is JWT
    await asyncio.sleep(120)  # replace with your app loop
    await site.aclose()


asyncio.run(main())
```

## End-to-end with lime-agents-sdk

```python
import asyncio
from lime_agents import LimeAgent
from lime_sites import LimeSite

async def demo() -> None:
    received = asyncio.Event()
    box: dict[str, str] = {}

    site = LimeSite()

    @site.on_login
    async def on_login(request_id: str, passport: str | None) -> None:
        if passport:
            box["jwt"] = passport
            received.set()

    req = await site.create_login_request()
    async with LimeAgent() as agent:
        await agent.approve(req.request_id)  # agent solves PoW internally
    await asyncio.wait_for(received.wait(), timeout=120)
    verified = await site.verify_passport(
        box["jwt"],
        expected_request_id=req.request_id,
    )
    assert verified.valid
    await site.aclose()
```

## Handler contract

| SSE `type` | `passport` arg | Your action |
|------------|----------------|-------------|
| `approved` | agent JWT string | `verify_passport(passport, expected_request_id=request_id)` → session |
| `expired` | `None` | Drop pending state for `request_id` |
| `keepalive` | (not delivered to handlers) | ignored by SDK |

## Production deployment

- Create **one** `LimeSite` at process startup — not per HTTP request.
- Optional shared `httpx.AsyncClient` via `http_client` for connection pooling.
- nginx `proxy_read_timeout` on `GET .../events` must be **≥ 310s** (LIME production default). SDK uses a dedicated **310s SSE read timeout** and reconnects on drops.
- Call `await site.aclose()` only on shutdown.

```python
import httpx
from lime_sites import LimeSite

http_client = httpx.AsyncClient(timeout=30.0)
site = LimeSite(http_client=http_client)

@site.on_login
async def on_login(request_id: str, passport: str | None) -> None:
    ...
```

## Authentication

Site HTTP calls use `X-Site-Token`.

1. Constructor `site_token="st_..."`
2. Else env `LIME_SITE_TOKEN`

Missing token → `AuthenticationError` at construct time (before loop check).

## Configuration

| Variable | Purpose |
|----------|---------|
| `LIME_SITE_TOKEN` | Site integration token (required) |
| `LIME_API_BASE` | API root with `/api/v1` (default `https://lime.pics/api/v1`) |

## API reference

### `LimeSite`

#### Constructor (keyword-only, **inside running asyncio loop**)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `site_token` | `None` | Falls back to `LIME_SITE_TOKEN` |
| `base_url` | `None` | Falls back to `LIME_API_BASE` |
| `timeout` | `30.0` | Per HTTP request timeout (seconds) |
| `max_retries` | `3` | Retries on 5xx / transport errors |
| `sse_backoff_base` | `0.5` | Initial SSE reconnect backoff (seconds) |
| `http_client` | `None` | Inject `httpx.AsyncClient` for tests / pooling |

#### Methods

| Method | Description |
|--------|-------------|
| `on_login(handler)` | Register async handler; use as `@site.on_login` decorator |
| `create_login_request()` | `POST /modules/agent-login/requests` → `LoginRequestResult` |
| `verify_passport(jwt, *, expected_request_id=None)` | JWKS RS256 verify → `PassportVerificationResult` |
| `aclose()` | Stop background dispatcher + close HTTP client |

Supports `async with LimeSite(...) as site:` (still requires running loop at `__aenter__`).

### Types

| Type | Fields |
|------|--------|
| `LoginRequestResult` | `request_id`, `status`, `expires_at` |
| `PassportVerificationResult` | `valid`, `claims` |

### Errors

| Exception | When |
|-----------|------|
| `AuthenticationError` | Missing/invalid site token |
| `RequestExpiredError` | JWT / binding expired on verify |
| `InvalidPassportError` | JWT verify failure |
| `RateLimitError` | HTTP 429 |
| `ApiError` | Other API errors |
| `LimeError` | Base class |

`RuntimeError` if `LimeSite()` is called without a running event loop.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
mypy src/lime_sites
pytest --cov=lime_sites --cov-fail-under=100
```

Live integration:

```bash
pip install lime-agents-sdk lime-sites-sdk
LIME_INTEGRATION=1 pytest tests/integration -v --ignore-glob='*'
```

Full cycle on production VPS (LIME monorepo): `python scripts/_run_both_sdks_integration_remote.py --runs 3`

## License

MIT — see [LICENSE](LICENSE).
