# lime-sites-sdk

Accept **AI agent login** on your site backend — create a request, get a Core-signed passport over SSE, verify locally with JWKS.

## Canonical docs

| Surface | URL |
|---------|-----|
| Hello (agents) | https://lime.pics/agent |
| Auth | https://lime.pics/auth.md |
| Flows | https://lime.pics/.well-known/agent-flows |
| Site login guide | https://lime.pics/docs/guides/site-login/ |
| Binding guide | https://lime.pics/docs/guides/site-binding/ |
| Machine package | https://lime.pics/.well-known/agent-context/ |
| GitHub | https://github.com/Mawyxx/lime-site-sdk |

Prefer lime.pics + GitHub over stale RTD mirrors.

```python
from lime_sites import LimeSite

site = LimeSite()  # LIME_SITE_TOKEN — construct inside a running asyncio loop

@site.on_login
async def handle_login(request_id: str, passport: str | None) -> None:
    if passport is None:
        return  # expired
    verified = await site.verify_passport(passport, expected_request_id=request_id)
    # issue YOUR session cookie from verified.claims

req = await site.create_login_request()
# show req.request_id on YOUR waiting screen → agent.login(request_id)
```

**What the SDK handles:** Site Token auth · login request · SSE passport delivery · JWKS verify · optional agent binding.

[![PyPI version](https://img.shields.io/pypi/v/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-site-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-site-sdk/actions/workflows/ci.yml)

**Docs:** [lime.pics/docs](https://lime.pics/docs/) · [auth.md](https://lime.pics/auth.md) · [GitHub](https://github.com/Mawyxx/lime-site-sdk)

---

## Installation

```bash
pip install lime-sites-sdk
export LIME_SITE_TOKEN=st_...   # from https://lime.pics — site portal
```

**Requirements:** Python 3.10+ · `httpx` · `PyJWT` · `cryptography`  
**Config:** one secret — `LIME_SITE_TOKEN` (or `site_token=`). Never give Site Token to the agent.

---

## Quick start (canonical) — FastAPI site login

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from lime_sites import InvalidPassportError, LimeSite

pending_logins: dict[str, object] = {}
site: LimeSite


@asynccontextmanager
async def lifespan(app: FastAPI):
    global site
    site = LimeSite()  # one LimeSite per process / site token

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        if passport is None:
            pending_logins.pop(request_id, None)
            return
        try:
            verified = await site.verify_passport(
                passport,
                expected_request_id=request_id,
            )
        except InvalidPassportError:
            pending_logins.pop(request_id, None)
            return
        pending_logins[request_id] = verified.claims  # set YOUR session

    yield
    await site.aclose()


app = FastAPI(lifespan=lifespan)


@app.post("/login/start")
async def start_login() -> dict[str, str]:
    req = await site.create_login_request()
    return {"request_id": req.request_id}
```

Copy-paste: [`examples/fastapi-login/`](examples/fastapi-login/).

**Agent worker** (separate package): [`lime-agents-sdk`](https://github.com/Mawyxx/lime-agents-sdk) → `await agent.login(request_id)`.

---

## Mental model

```text
LimeSite
├── Site login (primary)   create_login_request · on_login · verify_passport
├── Agent binding          create_binding_request · verify_binding_passport
└── Lifecycle              aclose()
```

| Credential | Header | Used for |
|------------|--------|----------|
| Opaque **Site Token** | `X-Site-Token` | Your backend ↔ LIME only |
| **Site passport JWT** | delivered on SSE | Session after `verify_passport` (`aud=lime-site-login`) |

Site login ≠ agent binding. MCP Bearer (`aud=mcp`) is **not** verified here — use [`lime-mcp-server-sdk`](https://github.com/Mawyxx/lime-mcp-server-sdk).

---

## Rules that prevent foot-guns

| Rule | Why |
|------|-----|
| **One `LimeSite` per site token per process** | One SSE connection |
| Construct inside a **running asyncio loop** | Dispatcher uses `create_task` |
| Keep `@site.on_login` handlers **fast** | Events dispatch sequentially |
| `passport is None` → **expired** | Clear pending state |

---

## Second scenario — Agent binding

**IS:** Bind a LIME `agent_id` to a signed-in human via Connect (`aud=lime-binding`). No SSE.  
**DO:** create → redirect human to `connect_url` → callback `?binding_code=` → exchange → `verify_binding_passport`.  
**NEVER:** JWT in redirect URL (query or fragment).

```python
req = await site.create_binding_request(redirect_uri="https://yoursite.example/bind/callback")
# persist req.binding_id ↔ user_id, redirect browser to req.connect_url
# callback: binding_code = query["binding_code"]
# POST /api/v1/modules/bindings/exchange with X-Site-Token + {"binding_code": ...}
#   → data.passport, then:
# verified = await site.verify_binding_passport(passport)
# → claims["binding_id"] / claims["agent_id"] (sub)
```

Canonical wire: [site-binding guide](https://lime.pics/docs/guides/site-binding/) · flow `agent_binding` in [agent-flows](https://lime.pics/.well-known/agent-flows).  
Example sketch: [`examples/binding/`](examples/binding/).

---

## Minimal end-to-end loop

With both SDKs installed (`lime-sites-sdk` + `lime-agents-sdk`):

```python
import asyncio

from lime_agents import LimeAgent
from lime_sites import LimeSite

async def main() -> None:
    received = asyncio.Event()
    box: dict[str, str] = {}

    site = LimeSite()

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        if passport:
            box["jwt"] = passport
            received.set()

    req = await site.create_login_request()

    async with LimeAgent() as agent:
        await agent.login(req.request_id)

    await asyncio.wait_for(received.wait(), timeout=120)
    verified = await site.verify_passport(box["jwt"], expected_request_id=req.request_id)
    print(verified.claims)
    await site.aclose()

asyncio.run(main())
```

Example: [`examples/minimal-loop/`](examples/minimal-loop/).

---

## API surface (summary)

| Method | Description |
|--------|-------------|
| `create_login_request()` | Start site login → `request_id` |
| `@site.on_login` | Handler `(request_id, passport \| None)` |
| `verify_passport(jwt, …)` | JWKS verify `aud=lime-site-login` |
| `create_binding_request(…)` | Start Connect binding → `binding_id` + `connect_url` |
| `verify_binding_passport(jwt)` | JWKS verify `aud=lime-binding` (after `?binding_code=` → exchange) |
| `aclose()` | Stop SSE / close client |

**Env:** `LIME_SITE_TOKEN` (required unless constructor), `LIME_API_BASE` (optional).

---

## Related packages

| Package | Role |
|---------|------|
| [`lime-agents-sdk`](https://github.com/Mawyxx/lime-agents-sdk) | Agent worker: `login(request_id)` + MCP client |
| [`lime-mcp-server-sdk`](https://github.com/Mawyxx/lime-mcp-server-sdk) | MCP RS: verify `aud=mcp` Bearer |

---

## Examples

| Path | Purpose |
|------|---------|
| [`examples/fastapi-login/`](examples/fastapi-login/) | Canonical site login |
| [`examples/minimal-loop/`](examples/minimal-loop/) | Site + agent E2E sketch |
| [`examples/binding/`](examples/binding/) | Connect binding sketch |

---

## Contributing

```bash
git clone https://github.com/Mawyxx/lime-site-sdk.git
cd lime-site-sdk
pip install -e ".[dev]"
ruff check src tests
mypy src/lime_sites
pytest --cov=lime_sites --cov-fail-under=100
```

---

## License

MIT — see [LICENSE](LICENSE).
