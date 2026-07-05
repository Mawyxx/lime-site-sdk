# Quick Start

## FastAPI lifespan pattern

Construct `LimeSite` inside a running event loop (e.g. FastAPI lifespan). The SDK starts
an SSE dispatcher that delivers approved passports to `@site.on_login` handlers.

```python
import asyncio

from lime_sites import LimeSite

async def main() -> None:
    received = asyncio.Event()
    box: dict[str, object] = {}
    site = LimeSite()  # LIME_SITE_TOKEN

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        box["request_id"] = request_id
        box["passport"] = passport
        received.set()

    req = await site.create_login_request()
    # Pass req.request_id to agent worker (lime-agents-sdk login)
    await asyncio.wait_for(received.wait(), timeout=120)

    if box.get("passport"):
        verified = await site.verify_passport(
            str(box["passport"]),
            expected_request_id=req.request_id,
        )
        print(verified.valid, verified.claims.get("sub"))

    await site.aclose()

asyncio.run(main())
```

## Step-by-step

1. **`create_login_request()`** — returns `request_id` (maps from API `login_request_id`)
2. **Hand off `request_id`** to agent worker out-of-band (queue, RPC, bot message)
3. **Agent approves** via [`lime-agents-sdk`](https://lime-agents-sdk.readthedocs.io/)
4. **SSE delivers** `agent_passport_jwt` to your `@site.on_login` handler
5. **`verify_passport(jwt, expected_request_id=...)`** — RS256 + JWKS + binding

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LIME_SITE_TOKEN` | Yes* | Site secret from LIME portal |
| `LIME_API_BASE` | No | Default `https://lime.pics/api/v1` |

## Production notes

- SSE proxy `read_timeout` should be **≥ 310 seconds**
- SSE delivery is **at-least-once** — make handlers idempotent on `request_id`
- Request body for create must be `{}` only (no extra fields)

See [LIME platform docs](https://lime.pics/docs) for HTTP reference.
