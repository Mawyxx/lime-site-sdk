# lime-sites-sdk

Accept **AI agent login** on your site backend — SSE passport + JWKS verify.

```python
site = LimeSite()  # LIME_SITE_TOKEN

@site.on_login
async def handle_login(request_id: str, passport: str | None) -> None:
    if passport:
        verified = await site.verify_passport(passport, expected_request_id=request_id)
        # YOUR session from verified.claims

req = await site.create_login_request()
```

[![PyPI](https://img.shields.io/pypi/v/lime-sites-sdk)](https://pypi.org/project/lime-sites-sdk/)
[![Docs](https://img.shields.io/badge/docs-lime.pics-00C853)](https://lime.pics/docs/guides/site-login/)

## Who is this for?

Site backends with a `site_token` from the [LIME portal](https://lime.pics).
Agent workers use [lime-agents-sdk](https://github.com/Mawyxx/lime-agents-sdk) instead.

**Canonical:** [auth.md](https://lime.pics/auth.md) · [site-login guide](https://lime.pics/docs/guides/site-login/) · [binding guide](https://lime.pics/docs/guides/site-binding/)

## Mental model

```text
LimeSite
├── Site login     create_login_request · on_login · verify_passport   ← primary
├── Agent binding  create_binding_request · verify_binding_passport
└── Lifecycle      aclose()
```

## Install

```bash
pip install lime-sites-sdk
export LIME_SITE_TOKEN=st_...
```

## Next pages

1. [Quick Start](quickstart.md)
2. [API Reference](api.md)
3. [Examples](examples.md)

Platform: [lime.pics/docs](https://lime.pics/docs#guide-siteSdk)
