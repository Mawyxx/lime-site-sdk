# API Reference

Each method below is a **separate section** with signature and parameters.

HTTP details: [LIME platform docs](https://lime.pics/docs#guide-siteSdk).

---

## `LimeSite` — method index

| Method | What it does | Returns |
|--------|--------------|---------|
| [`LimeSite()`](#limesite) | Start SSE dispatcher + HTTP client | `LimeSite` |
| [`on_login()`](#on_login) | Register handler for approved/expired SSE events | decorator |
| [`create_login_request()`](#create_login_request) | Start login; get `request_id` for agent | `LoginRequestResult` |
| [`verify_passport()`](#verify_passport) | Validate passport JWT (JWKS + binding) | `PassportVerificationResult` |
| [`aclose()`](#aclose) | Stop SSE + close HTTP client | `None` |

!!! tip "Typical flow"
    1. `site = LimeSite()` inside running asyncio loop (FastAPI lifespan).
    2. `@site.on_login` handler — receives passport when agent approves.
    3. `req = await site.create_login_request()` — pass `req.request_id` to agent worker
       ([lime-agents-sdk](https://lime-agents-sdk.readthedocs.io/)).
    4. In handler: `await site.verify_passport(jwt, expected_request_id=req.request_id)`.

---

## Class overview

::: lime_sites.LimeSite
    options:
      heading_level: 2
      show_root_heading: true
      members: false

---

## Lifecycle

### `LimeSite()`

::: lime_sites.LimeSite.__init__
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

!!! warning "Event loop required"
    Call **only** inside a running asyncio loop. `asyncio.run()` and FastAPI lifespan are OK;
    module-level `site = LimeSite()` at import time is **not**.

### `aclose()`

::: lime_sites.LimeSite.aclose
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

---

## SSE handler

### `on_login()`

::: lime_sites.LimeSite.on_login
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

**Handler signature:**

```python
async def handler(request_id: str, passport: str | None) -> None:
    ...
```

| Argument | Meaning |
|----------|---------|
| `request_id` | Login request id from create (or from SSE event) |
| `passport` | RS256 JWT string on **approved**; `None` on **expired** |

---

## Login flow

### `create_login_request()`

::: lime_sites.LimeSite.create_login_request
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

### `verify_passport()`

::: lime_sites.LimeSite.verify_passport
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

---

## Result types

### `LoginRequestResult`

::: lime_sites.LoginRequestResult
    options:
      heading_level: 3
      show_root_heading: true

### `PassportVerificationResult`

::: lime_sites.PassportVerificationResult
    options:
      heading_level: 3
      show_root_heading: true

---

## Errors

| Exception | When |
|-----------|------|
| `AuthenticationError` | Missing `LIME_SITE_TOKEN` |
| `InvalidPassportError` | JWT signature, expiry, aud, or `request_id` mismatch |
| `RequestExpiredError` | Login request expired before approve |
| `ApiError` | LIME API business error |
| `RateLimitError` | HTTP 429 |

### `InvalidPassportError`

::: lime_sites.InvalidPassportError
    options:
      heading_level: 4
      show_root_heading: true

### `LimeError`

::: lime_sites.LimeError
    options:
      heading_level: 4
      show_root_heading: true

### `AuthenticationError`

::: lime_sites.AuthenticationError
    options:
      heading_level: 4
      show_root_heading: true

### `RequestExpiredError`

::: lime_sites.RequestExpiredError
    options:
      heading_level: 4
      show_root_heading: true

### `RateLimitError`

::: lime_sites.RateLimitError
    options:
      heading_level: 4
      show_root_heading: true

### `ApiError`

::: lime_sites.ApiError
    options:
      heading_level: 4
      show_root_heading: true

!!! note "Legacy type"
    `LoginResult` remains for backward-compatible SSE parsing; prefer `@site.on_login`
    with `verify_passport()` in new integrations.
