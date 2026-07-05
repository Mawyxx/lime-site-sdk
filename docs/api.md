# API Reference

Start with [Home](index.md) for the login flow diagram and `LimeSite` method tree.

Each method below has its **own section**. HTTP routes: [LIME platform docs](https://lime.pics/docs).

---

## Method order (site login only)

| Step | Method |
|------|--------|
| 1 | `LimeSite()` |
| 2 | `@site.on_login` |
| 3 | `create_login_request()` |
| 4 | `verify_passport()` (in handler) |
| 5 | `aclose()` |

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
