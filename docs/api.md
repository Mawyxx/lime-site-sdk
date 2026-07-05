# API Reference

Auto-generated from Google-style docstrings. For HTTP endpoints, see
[LIME platform documentation](https://lime.pics/docs).

## LimeSite

::: lime_sites.LimeSite
    options:
      show_root_heading: true
      members:
        - __init__
        - on_login
        - create_login_request
        - verify_passport
        - aclose

## Result types

::: lime_sites.LoginRequestResult
::: lime_sites.PassportVerificationResult

## Errors

::: lime_sites.InvalidPassportError
::: lime_sites.LimeError
::: lime_sites.AuthenticationError
::: lime_sites.RequestExpiredError
::: lime_sites.RateLimitError
::: lime_sites.ApiError

!!! note "Legacy type"
    `LoginResult` remains for backward-compatible SSE parsing; prefer `@site.on_login`
    with `verify_passport()` in new integrations.
