# Examples

## FastAPI integration

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from lime_sites import LimeSite

site: LimeSite | None = None

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global site
    site = LimeSite()

    @site.on_login
    async def on_login(request_id: str, passport: str | None) -> None:
        if passport is None:
            return
        verified = await site.verify_passport(
            passport, expected_request_id=request_id
        )
        # Map verified.claims["user_id"] to your site session

    yield
    await site.aclose()

app = FastAPI(lifespan=lifespan)
```

## Idempotent SSE handler

SSE may deliver the same event more than once:

```python
handled: set[str] = set()

@site.on_login
async def handle(request_id: str, passport: str | None) -> None:
    if request_id in handled:
        return
    handled.add(request_id)
    ...
```

## Mapping `user_id` to site sessions

Passport JWT `user_id` is the **LIME owner UUID**, not your site's user primary key.
Maintain a correlation map keyed by `request_id`:

```python
pending: dict[str, str] = {}  # request_id -> site_user_id

req = await site.create_login_request()
pending[req.request_id] = current_site_user_id

@site.on_login
async def handle(request_id: str, passport: str | None) -> None:
    site_user = pending.pop(request_id, None)
    if not passport or not site_user:
        return
    verified = await site.verify_passport(
        passport, expected_request_id=request_id
    )
    owner_uuid = verified.claims["user_id"]
    agent_uuid = verified.claims["sub"]
    # Link site_user + owner_uuid + agent_uuid in your DB
```

## Anti-patterns

| Mistake | Correct approach |
|---------|------------------|
| Create `LimeSite()` outside running loop | Use FastAPI lifespan or `asyncio.run` |
| Block waiting on SSE in HTTP handler | Use `@site.on_login` dispatcher |
| Use MCP JWT verifier for passport | Passport is `aud=lime-site-login` — use `verify_passport` |
| Skip `expected_request_id` | Always bind JWT to the login request you created |
