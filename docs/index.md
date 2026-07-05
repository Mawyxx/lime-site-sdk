# lime-sites-sdk

Official Python SDK for **LIME site backends**. Create login requests, receive agent
passports over SSE, and verify RS256 JWTs via Core JWKS — async-first with an auto-started
event dispatcher.

[![PyPI](https://img.shields.io/pypi/v/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![Documentation](https://readthedocs.org/projects/lime-sites-sdk/badge/?version=latest)](https://lime-sites-sdk.readthedocs.io/)
[![GitHub](https://img.shields.io/github/stars/Mawyxx/lime-site-sdk?style=social)](https://github.com/Mawyxx/lime-site-sdk)

## Key features

- `await site.create_login_request()` — start headless site login
- Perpetual SSE dispatcher with `@site.on_login` handlers
- `await site.verify_passport(jwt)` — JWKS RS256 verify with `request_id` binding
- FastAPI lifespan pattern documented
- Typed errors and 100% test coverage

## Credential boundary

| Role | Credential | SDK |
|------|------------|-----|
| **Site backend** | **`X-Site-Token` + verify passport JWT** | **This package** |
| Agent worker | `X-Agent-Token` + approve | [lime-agents-sdk](https://lime-agents-sdk.readthedocs.io/) |
| MCP resource server | Verify Bearer MCP JWT | [lime-mcp-server-sdk](https://lime-mcp-server-sdk.readthedocs.io/) |

## Platform documentation

- [LIME platform docs — Site SDK](https://lime.pics/docs#guide-siteSdk)

## Minimal example

```python
# pip install lime-sites-sdk
import asyncio
from lime_sites import LimeSite

async def main() -> None:
    site = LimeSite()  # LIME_SITE_TOKEN; requires running event loop

    @site.on_login
    async def handle(request_id: str, passport: str | None) -> None:
        if passport:
            verified = await site.verify_passport(
                passport, expected_request_id=request_id
            )
            print(verified.claims["sub"])

    req = await site.create_login_request()
    # hand req.request_id to agent worker (lime-agents-sdk)
    await site.aclose()

asyncio.run(main())
```

## Next steps

- [Installation](installation.md)
- [Quick Start](quickstart.md)
- [API Reference](api.md) — **method index + one section per method**
- [Examples](examples.md)

## API at a glance

| Step | Call |
|------|------|
| 1. Start (inside asyncio loop) | `site = LimeSite()` |
| 2. Register SSE handler | `@site.on_login` async def … |
| 3. Create login | `req = await site.create_login_request()` |
| 4. Hand off to agent | pass `req.request_id` OOB |
| 5. In handler, verify JWT | `await site.verify_passport(jwt, expected_request_id=…)` |
| 6. Shutdown | `await site.aclose()` |

Details: [API Reference](api.md).
