# lime-sites-sdk — Accept AI Agents on Your Site (JWT + JWKS)

**`lime-sites-sdk`** is the official **Python site SDK** for [LIME](https://lime.pics) — **headless AI agent login** for backends that want to accept autonomous agents without browsers, OAuth redirects, or QR codes. Create a login request, receive a signed **agent passport JWT** over **SSE events**, and **verify** it offline with **JWKS** (`aud=lime-site-login`) — all with `X-Site-Token` and a small async API.

Use this package on **site backends** (FastAPI, Django ASGI, workers). Pair with [`lime-agents-sdk`](https://github.com/Mawyxx/lime-agents-sdk) on the agent worker that calls `login(request_id)`.

[![PyPI version](https://img.shields.io/pypi/v/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-site-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-site-sdk/actions/workflows/ci.yml)
[![MCP compatible](https://img.shields.io/badge/MCP-compatible-00C853)](https://modelcontextprotocol.io/)

**📖 Platform API docs:** [https://lime.pics/docs](https://lime.pics/docs#guide-siteSdk)  
**📦 This SDK:** [github.com/Mawyxx/lime-site-sdk](https://github.com/Mawyxx/lime-site-sdk)  
**🌐 Platform:** [https://lime.pics](https://lime.pics)

---

## Why lime-sites-sdk?

| Problem | SDK solution |
|---------|----------------|
| Manual site login API + SSE parsing | `create_login_request()` + background **SSE dispatcher** |
| JWKS fetch, kid cache, RS256 checks | `verify_passport()` with in-memory JWKS cache |
| Blocking wait per HTTP request | `@site.on_login` handlers — map `request_id` → session |
| Fragile site credentials | Env-based `LIME_SITE_TOKEN`, typed errors, `py.typed` |

### Site passport JWT flow (this SDK)

LIME delivers the **cryptographic passport** to the **site backend**, not to the agent worker.

| Step | Who | What happens |
|------|-----|----------------|
| 1 | **Site** (`lime-sites-sdk`) | `create_login_request()` → `request_id` |
| 2 | **Your app** | Hand `request_id` to the agent (queue, RPC, UI) |
| 3 | **Agent** ([`lime-agents-sdk`](https://github.com/Mawyxx/lime-agents-sdk)) | `await agent.login(request_id)` — PoW + approve |
| 4 | **Site** (`@site.on_login`) | SSE `approved` → **passport JWT** string |
| 5 | **Site** | `verify_passport(jwt, expected_request_id=…)` → claims → session |

| Artifact | Audience | TTL (typical) | Verified by |
|----------|----------|---------------|-------------|
| **Site passport JWT** | Site backend (SSE) | Short-lived signed passport (`aud=lime-site-login`) | **`lime-sites-sdk`** via Core JWKS |

> **Not this SDK:** MCP access JWTs (`aud=mcp`, ~5 min) are issued to **agent workers** via [`lime-agents-sdk`](https://github.com/Mawyxx/lime-agents-sdk). Sites do not receive or verify MCP tokens.

---

## Installation

```bash
pip install lime-sites-sdk
```

Latest from GitHub:

```bash
pip install git+https://github.com/Mawyxx/lime-site-sdk.git
```

**Requirements:** Python 3.10+ · runtime deps: `httpx`, `PyJWT`, `cryptography`

---

## Quick start

### Scenario A — FastAPI site backend (production pattern)

**Story:** One `LimeSite` per process starts a perpetual SSE connection. When an agent approves login, your `@site.on_login` handler receives the passport JWT, verifies it, and binds claims to the user session.

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from lime_sites import InvalidPassportError, LimeSite

site: LimeSite
pending_logins: dict[str, object] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global site
    site = LimeSite()  # LIME_SITE_TOKEN=st_... — server-side secret only

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        if passport is None:
            pending_logins.pop(request_id, None)  # expired — no JWT delivered
            return
        try:
            verified = await site.verify_passport(
                passport,
                expected_request_id=request_id,
            )
        except InvalidPassportError:
            pending_logins.pop(request_id, None)
            return
        pending_logins[request_id] = verified.claims  # issue session / cookie

    yield
    await site.aclose()


app = FastAPI(lifespan=lifespan)


@app.post("/login/start")
async def start_login() -> dict[str, str]:
    req = await site.create_login_request()
    # Return request_id to client; agent worker calls login(req.request_id)
    return {"request_id": req.request_id}
```

**Rules:**

| Rule | Why |
|------|-----|
| **One `LimeSite` per site token per process** | One SSE connection per site |
| Construct inside a **running asyncio loop** | Dispatcher uses `asyncio.create_task` |
| Keep `@site.on_login` handlers **fast** | Events are dispatched sequentially |
| `passport is None` → **expired** | Clear pending state for that `request_id` |

---

### Scenario B — Minimal loop + full cycle with `lime-agents-sdk`

**Story:** End-to-end headless login — site creates request, agent approves, site verifies passport JWT.

```python
import asyncio

from lime_agents import LimeAgent
from lime_sites import InvalidPassportError, LimeSite

async def main() -> None:
    received = asyncio.Event()
    box: dict[str, str] = {}

    site = LimeSite()  # LIME_SITE_TOKEN — must be inside async main (running loop)

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        if passport:
            box["jwt"] = passport
            received.set()

    req = await site.create_login_request()

    async with LimeAgent() as agent:  # LIME_AGENT_TOKEN
        approve = await agent.login(req.request_id)
        print(approve.status)  # APPROVED — passport JWT is delivered to site via SSE, not to agent

    await asyncio.wait_for(received.wait(), timeout=120)

    try:
        verified = await site.verify_passport(
            box["jwt"],
            expected_request_id=req.request_id,
        )
    except InvalidPassportError as exc:
        print(f"passport invalid: {exc}")
        await site.aclose()
        return

    print(verified.claims["agent_id"])  # verified.valid is always True on success
    await site.aclose()


asyncio.run(main())
```

**SSE dispatcher (automatic):**

1. `GET /api/v1/modules/agent-login/events` (`text/event-stream`, `X-Site-Token`)
2. Parse `approved` / `expired` / `keepalive` with reconnect + backoff
3. Call registered handlers: `(request_id, passport | None)`
4. Stop on `await site.aclose()`

**Agent side (separate package):** [`lime-agents-sdk`](https://github.com/Mawyxx/lime-agents-sdk) → `await agent.login(request_id)` — PoW + approve.

---

## Features

- **Headless AI agent login** — no browser, QR, or OAuth redirect on the site
- **Background SSE dispatcher** — perpetual event stream with auto-reconnect (310s read timeout)
- **`@site.on_login` handlers** — `approved` → JWT string; `expired` → `passport=None`
- **JWKS passport verification** — RS256, `aud=lime-site-login`, cached keys, `kid` refresh
- **`create_login_request()`** — `POST /modules/agent-login/requests` with `X-Site-Token`
- **Typed results** — `LoginRequestResult`, `PassportVerificationResult`, mypy-clean public API

---

## API reference (summary)

### `LimeSite`

Construct **inside a running asyncio loop** (e.g. FastAPI lifespan, `asyncio.run`).

| Method | Description |
|--------|-------------|
| `@site.on_login` / `site.on_login(handler)` | Register handler for SSE login events |
| `await site.create_login_request()` | Start login → `LoginRequestResult` |
| `await site.verify_passport(jwt, *, expected_request_id=None)` | JWKS RS256 verify → `PassportVerificationResult` |
| `await site.aclose()` | Stop dispatcher + close HTTP client |

**Constructor highlights:** `site_token` / `LIME_SITE_TOKEN`, `base_url` / `LIME_API_BASE` (default `https://lime.pics/api/v1`), `timeout`, `max_retries`, `sse_backoff_base`, injectable `http_client`.

### `verify_passport` checks

- Signature valid against `GET /api/v1/core/.well-known/jwks.json`
- `aud == "lime-site-login"`
- `exp` / `iat` within platform TTL
- Optional `expected_request_id` matches JWT `request_id` claim

**Claims** (typical): `agent_id`, `user_id`, `user_kyc_level`, `agent_reputation`, `request_id`, `exp`, `iat`.

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LIME_SITE_TOKEN` | Yes* | Site integration token (`st_...`) from the LIME portal |
| `LIME_API_BASE` | No | API root, e.g. `https://lime.pics/api/v1` |

\*Unless `site_token=` is passed to the constructor.

### Errors

All inherit from `LimeError`: `AuthenticationError`, `InvalidPassportError`, `RequestExpiredError`, `RateLimitError`, `ApiError`.

`RuntimeError` if `LimeSite()` is constructed without a running event loop.

---

## Production notes

- Create **one** `LimeSite` at worker startup — not per HTTP request.
- nginx `proxy_read_timeout` on `GET .../events` should be **≥ 310s** (matches SDK SSE read timeout).
- Store `request_id` → pending session in Redis/DB; complete session in `@site.on_login`.
- Never expose `LIME_SITE_TOKEN` to frontend JavaScript — server-side only.

---

## Related packages

| Package | Role |
|---------|------|
| [`lime-agents-sdk`](https://github.com/Mawyxx/lime-agents-sdk) | Agent worker: `login(request_id)`, MCP OAuth client |
| [`lime-mcp-server-sdk`](https://github.com/Mawyxx/lime-mcp-server-sdk) | MCP resource server: verify MCP Bearer JWT (separate from site passport) |

---

## Contributing

Issues and pull requests: [github.com/Mawyxx/lime-site-sdk](https://github.com/Mawyxx/lime-site-sdk)

```bash
git clone https://github.com/Mawyxx/lime-site-sdk.git
cd lime-site-sdk
pip install -e ".[dev]"
ruff check src tests
mypy src/lime_sites
pytest --cov=lime_sites --cov-fail-under=100
```

CI runs on Python 3.10–3.13 with **100% line coverage** on `src/lime_sites`.

---

## License

MIT — see [LICENSE](LICENSE).
