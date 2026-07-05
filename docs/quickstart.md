# Quick Start

This SDK handles **one job**: site login on your backend. For agent-side approve, see
[lime-agents-sdk](https://lime-agents-sdk.readthedocs.io/).

---

## Step-by-step (method order matters)

| Step | What you do | Method |
|------|-------------|--------|
| 1 | Create client **inside** `asyncio.run()` or FastAPI lifespan | `site = LimeSite()` |
| 2 | Register handler **before** creating login | `@site.on_login` |
| 3 | Start login; send `request_id` to agent | `await site.create_login_request()` |
| 4 | Agent approves (other SDK) | `lime-agents-sdk` → `login()` |
| 5 | Handler receives JWT | automatic via SSE |
| 6 | Verify JWT; open your session | `await site.verify_passport(...)` |
| 7 | Shutdown | `await site.aclose()` |

---

## Full example

```python
import asyncio

from lime_sites import LimeSite

async def main() -> None:
    received = asyncio.Event()
    box: dict[str, object] = {}

    site = LimeSite()  # LIME_SITE_TOKEN from env

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        box["request_id"] = request_id
        box["passport"] = passport
        received.set()

    req = await site.create_login_request()
    print("Send to agent worker:", req.request_id)

    await asyncio.wait_for(received.wait(), timeout=120)

    if box.get("passport"):
        verified = await site.verify_passport(
            str(box["passport"]),
            expected_request_id=req.request_id,
        )
        if verified.valid:
            agent_id = verified.claims["sub"]
            user_id = verified.claims["user_id"]
            # → create YOUR session here (cookie, JWT, DB row)

    await site.aclose()

asyncio.run(main())
```

---

## Handler arguments

```python
async def handler(request_id: str, passport: str | None) -> None:
```

| Argument | When | What to do |
|----------|------|------------|
| `passport` is a string | Agent approved | Call `verify_passport(passport, expected_request_id=request_id)` |
| `passport` is `None` | Request expired | Show "try again" to user |

---

## FastAPI lifespan

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from lime_sites import LimeSite

@asynccontextmanager
async def lifespan(app: FastAPI):
    site = LimeSite()

    @site.on_login
    async def on_login(request_id: str, passport: str | None) -> None:
        if passport:
            verified = await site.verify_passport(
                passport, expected_request_id=request_id
            )
            # store in app state, Redis, etc.

    app.state.lime_site = site
    yield
    await site.aclose()

app = FastAPI(lifespan=lifespan)
```

---

## Environment variables

| Variable | Required | Default |
|----------|----------|---------|
| `LIME_SITE_TOKEN` | Yes* | — |
| `LIME_API_BASE` | No | `https://lime.pics/api/v1` |

\*Or `site_token=` to `LimeSite()`.

---

## Production notes

- Construct `LimeSite()` only when asyncio loop is **already running**
- SSE proxy timeout ≥ **310 seconds**
- Handlers may fire more than once for the same `request_id` — make them idempotent

HTTP reference: [lime.pics/docs](https://lime.pics/docs)
