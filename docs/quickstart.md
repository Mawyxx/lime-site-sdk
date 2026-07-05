# Quick Start

Site login on **your backend**. Agent approve is
[lime-agents-sdk](https://lime-agents-sdk.readthedocs.io/).

## Method order

| Step | Method | Notes |
|------|--------|-------|
| 1 | `LimeSite()` | Inside running asyncio loop |
| 2 | `@site.on_login` | Register **before** create |
| 3 | `create_login_request()` | Send `request_id` to agent |
| 4 | Agent `login()` | Other SDK |
| 5 | `verify_passport()` | In handler when SSE fires |
| 6 | `aclose()` | On shutdown |

## Full example

```python
import asyncio

from lime_sites import LimeSite

async def main() -> None:
    received = asyncio.Event()
    box: dict[str, object] = {}

    site = LimeSite()

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
            # create YOUR session here

    await site.aclose()

asyncio.run(main())
```

## Handler arguments

```python
async def handler(request_id: str, passport: str | None) -> None:
```

| Argument | When | Action |
|----------|------|--------|
| `passport` is `str` | Agent approved | `verify_passport(passport, expected_request_id=request_id)` |
| `passport` is `None` | Request expired | Show "try again" to user |

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
            # store verified.claims in app state / Redis

    app.state.lime_site = site
    yield
    await site.aclose()

app = FastAPI(lifespan=lifespan)
```

## Environment variables

| Variable | Required | Default |
|----------|----------|---------|
| `LIME_SITE_TOKEN` | Yes* | — |
| `LIME_API_BASE` | No | `https://lime.pics/api/v1` |

\*Or `site_token=` to `LimeSite()`.

!!! warning "Production"
    - Create `LimeSite()` only when asyncio loop is **running**
    - SSE proxy timeout ≥ **310 seconds**
    - Make `@site.on_login` idempotent on `request_id`

HTTP reference: [lime.pics/docs](https://lime.pics/docs)
