# lime-sites-sdk

Python library for **your website backend** — the server that runs your site and creates
user sessions.

[![PyPI](https://img.shields.io/pypi/v/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![Documentation](https://readthedocs.org/projects/lime-sites-sdk/badge/?version=latest)](https://lime-sites-sdk.readthedocs.io/)
[![GitHub](https://img.shields.io/github/stars/Mawyxx/lime-site-sdk?style=social)](https://github.com/Mawyxx/lime-site-sdk)

---

## Who is this for?

You registered a **site** in the [LIME portal](https://lime.pics) and got a secret
`site_token`. This SDK runs on **your backend** (FastAPI, Django ASGI, etc.) to:

1. Start a login when a user wants to sign in through an agent
2. Wait for the agent to approve
3. Verify the passport and create **your** local session

You do **not** need this SDK in the agent worker — that side uses
[lime-agents-sdk](https://lime-agents-sdk.readthedocs.io/).

---

## One scenario — site login (this SDK does only this)

There is no MCP in this package. The full login story:

```
YOUR BACKEND (this SDK)              AGENT WORKER (lime-agents-sdk)
        │                                      │
        │  1. create_login_request()           │
        │     → request_id                     │
        │─────────────────────────────────────>│  2. login(request_id)
        │                                      │
        │  3. SSE: passport arrives              │
        │     @site.on_login handler fires     │
        │  4. verify_passport(jwt)             │
        │  5. create YOUR session/cookie       │
```

---

## Class structure: `LimeSite`

```
LimeSite
│
├─── SETUP (inside running asyncio loop — e.g. FastAPI lifespan)
│    site = LimeSite()              reads LIME_SITE_TOKEN; starts SSE listener
│    await site.aclose()            stop SSE + HTTP on shutdown
│
├─── STEP 1 — Register handler (before create_login_request)
│    @site.on_login
│    async def handler(request_id, passport): ...
│         passport = JWT string when approved; None when expired
│
├─── STEP 2 — Start login
│    req = await site.create_login_request()   → LoginRequestResult
│         pass req.request_id to agent worker
│
└─── STEP 3 — Verify passport (inside handler)
     verified = await site.verify_passport(jwt, expected_request_id=...)
              → PassportVerificationResult
              map verified.claims to your user session
```

Method signatures: [API Reference](api.md).

---

## Minimal example

```python
import asyncio
from lime_sites import LimeSite

async def main() -> None:
    site = LimeSite()  # must be inside asyncio.run() or FastAPI lifespan

    @site.on_login
    async def on_login(request_id: str, passport: str | None) -> None:
        if passport:
            ok = await site.verify_passport(passport, expected_request_id=request_id)
            if ok.valid:
                print("User agent:", ok.claims["sub"])

    req = await site.create_login_request()
    print("Give this to agent:", req.request_id)
    # ... wait for handler; then await site.aclose()

asyncio.run(main())
```

---

## What you need before coding

| Item | Where to get it |
|------|-----------------|
| `LIME_SITE_TOKEN` | LIME portal → your site → copy token once |
| Agent approval | Agent worker calls `login(request_id)` — [lime-agents-sdk](https://lime-agents-sdk.readthedocs.io/) |

Optional: `LIME_API_BASE` — default `https://lime.pics/api/v1`.

---

## Install

```bash
pip install lime-sites-sdk
```

Details: [Installation](installation.md)

---

## Other LIME SDKs

| SDK | Your role |
|-----|-----------|
| [lime-agents-sdk](https://lime-agents-sdk.readthedocs.io/) | Agent worker (approves login) |
| **lime-sites-sdk** (this) | Website backend |
| [lime-mcp-server-sdk](https://lime-mcp-server-sdk.readthedocs.io/) | MCP server (separate product) |

Platform HTTP reference: [lime.pics/docs](https://lime.pics/docs#guide-siteSdk)

---

## Next pages

1. [Quick Start](quickstart.md) — FastAPI pattern step by step
2. [API Reference](api.md) — every method
3. [Examples](examples.md) — idempotent handlers, session mapping
