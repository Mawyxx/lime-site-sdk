# LIME Sites SDK

[![PyPI version](https://img.shields.io/pypi/v/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-sait-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-sait-sdk/actions/workflows/ci.yml)

Official Python SDK for [LIME](https://lime.pics) site backends. Async-first client: create login requests, wait for agent approval over SSE (with reconnect), verify JWT passports via JWKS.

> **Repository:** [lime-sait-sdk](https://github.com/Mawyxx/lime-sait-sdk) · **PyPI:** `lime-sites-sdk` · **Import:** `from lime_sites import LimeSite`

Pair with [lime-agents-sdk](https://github.com/Mawyxx/lime-agents-sdk) on the agent worker side.

## Installation

```bash
pip install lime-sites-sdk
```

Install the latest commit from GitHub:

```bash
pip install git+https://github.com/Mawyxx/lime-sait-sdk.git
```

**Requirements:** Python 3.10+

## Quick start

```python
from lime_sites import LimeSite

site = LimeSite()  # LIME_SITE_TOKEN

req = await site.create_login_request()
# → pass req.request_id to your agent worker (lime-agents-sdk approve)

login = await site.wait_for_login(req.request_id)
verified = await site.verify_passport(
    login.agent_passport_jwt,
    expected_request_id=req.request_id,
)
assert verified.valid
await site.aclose()
```

## Production example

```python
from lime_sites import (
    LimeSite,
    AuthenticationError,
    RequestExpiredError,
    InvalidPassportError,
    TimeoutError,
    ApiError,
)


async def handle_agent_login() -> dict | None:
    try:
        async with LimeSite() as site:
            req = await site.create_login_request()
            await notify_agent_worker(req.request_id)

            login = await site.wait_for_login(req.request_id, timeout=120.0)
            verified = await site.verify_passport(
                login.agent_passport_jwt,
                expected_request_id=req.request_id,
            )
            return verified.claims
    except TimeoutError:
        return None
    except RequestExpiredError:
        return None
    except InvalidPassportError:
        return None
    except ApiError as exc:
        print(f"[{exc.code}] {exc.message}")
        return None
```

## Authentication

Site HTTP calls use the `X-Site-Token` header.

**Resolution order:**

1. Constructor argument `site_token="st_..."`
2. Environment variable `LIME_SITE_TOKEN`

If neither is set, construction raises `AuthenticationError`.

Obtain the site token once when registering a site in the LIME owner portal. Store it as a server-side secret.

## Configuration

| Variable | Purpose |
|----------|---------|
| `LIME_SITE_TOKEN` | Site integration token (required) |
| `LIME_API_BASE` | API root including `/api/v1` (default `https://lime.pics/api/v1`) |

**SSE / proxy:** nginx (or similar) read timeout should be **≥ 310s** for long-lived event streams. The SDK reconnects automatically; default `wait_for_login` budget is 120s.

## API reference

### `LimeSite`

Async client for site-backend operations.

#### Constructor

All arguments are keyword-only.

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
| `create_login_request()` | `LoginRequestResult` | `POST /modules/agent-login/requests` |
| `wait_for_login(request_id, *, timeout=120.0)` | `LoginResult` | SSE until approved or expired |
| `verify_passport(jwt, *, expected_request_id=None)` | `PassportVerificationResult` | JWKS RS256 verify |
| `aclose()` | `None` | Close owned HTTP client |

Supports `async with LimeSite(...) as site:`.

### Types

| Type | Fields |
|------|--------|
| `LoginRequestResult` | `request_id`, `status`, `expires_at` |
| `LoginResult` | `request_id`, `agent_passport_jwt`, `redirect_url?` |
| `PassportVerificationResult` | `valid`, `claims` |

### Errors

| Exception | When |
|-----------|------|
| `AuthenticationError` | Missing/invalid site token |
| `RequestExpiredError` | SSE `expired` for waited request |
| `InvalidPassportError` | JWT verify failure |
| `TimeoutError` | `wait_for_login` exceeded timeout |
| `RateLimitError` | HTTP 429 |
| `ApiError` | Other API errors |
| `LimeError` | Base class |

## Integration pattern

1. Site backend calls `create_login_request()`.
2. Deliver `request_id` to agent worker (queue, RPC, bot message).
3. Agent worker runs `lime-agents-sdk` `approve(request_id)`.
4. Site backend calls `wait_for_login(request_id)` then `verify_passport(...)`.
5. Create local session from verified claims.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
mypy src/lime_sites
pytest --cov=lime_sites --cov-fail-under=100
```

Live integration (requires tokens):

```bash
LIME_INTEGRATION=1 pytest tests/integration -v
```

## License

MIT — see [LICENSE](LICENSE).
