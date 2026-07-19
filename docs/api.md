# API Reference

Read [Home](index.md) for the flow diagram and method table.

HTTP routes: [LIME platform docs](https://lime.pics/docs).

## Signature cheat sheet

<div class="sig-cheat" markdown="1">

```python
site = LimeSite(site_token: str | None = None, base_url: str | None = None, ...)

@site.on_login
async def handler(request_id: str, passport: str | None) -> None: ...

await site.create_login_request() -> LoginRequestResult

await site.verify_passport(
    jwt: str,
    *,
    expected_request_id: str | None = None,
) -> PassportVerificationResult

await site.create_binding_request(*, redirect_uri: str) -> BindingRequestResult

await site.verify_binding_passport(jwt: str) -> PassportVerificationResult

await site.aclose() -> None
```

</div>

Minimum setup: `LimeSite()` reads `LIME_SITE_TOKEN` from the environment.

## Method order

| Step | Method |
|------|--------|
| 1 | [`LimeSite()`](#lime_sites.LimeSite.__init__) |
| 2 | [`on_login()`](#lime_sites.LimeSite.on_login) |
| 3 | [`create_login_request()`](#lime_sites.LimeSite.create_login_request) |
| 4 | [`verify_passport()`](#lime_sites.LimeSite.verify_passport) |
| 5 | [`create_binding_request()`](#lime_sites.LimeSite.create_binding_request) |
| 6 | [`verify_binding_passport()`](#lime_sites.LimeSite.verify_binding_passport) |
| 7 | [`aclose()`](#lime_sites.LimeSite.aclose) |

## Class overview

::: lime_sites.LimeSite
    options:
      heading_level: 2
      show_root_heading: true
      members: false

## Lifecycle

::: lime_sites.LimeSite.__init__
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

!!! warning "Event loop required"
    Call **only** inside a running asyncio loop.

::: lime_sites.LimeSite.aclose
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

## SSE handler

::: lime_sites.LimeSite.on_login
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

Handler signature:

```python
async def handler(request_id: str, passport: str | None) -> None:
    ...
```

| Argument | Meaning |
|----------|---------|
| `request_id` | Login request id |
| `passport` | JWT on **approved**; `None` on **expired** |

## Login flow

::: lime_sites.LimeSite.create_login_request
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_sites.LimeSite.verify_passport
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

## Agent Binding

::: lime_sites.LimeSite.create_binding_request
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_sites.LimeSite.verify_binding_passport
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

## Result types

::: lime_sites.LoginRequestResult
    options:
      heading_level: 3
      show_root_heading: true

::: lime_sites.BindingRequestResult
    options:
      heading_level: 3
      show_root_heading: true

::: lime_sites.PassportVerificationResult
    options:
      heading_level: 3
      show_root_heading: true

## Errors

| Exception | When |
|-----------|------|
| `AuthenticationError` | Missing `LIME_SITE_TOKEN` |
| `InvalidPassportError` | JWT invalid, or `request_id` / `binding_id` mismatch |
| `RequestExpiredError` | Login expired before approve |
| `ApiError` | LIME API business error |
| `RateLimitError` | HTTP 429 |

::: lime_sites.InvalidPassportError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_sites.LimeError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_sites.AuthenticationError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_sites.RequestExpiredError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_sites.RateLimitError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_sites.ApiError
    options:
      heading_level: 3
      show_root_heading: true

!!! note "Legacy type"
    `LoginResult` is for backward-compatible SSE parsing; prefer `@site.on_login` +
    `verify_passport()` in new code.
