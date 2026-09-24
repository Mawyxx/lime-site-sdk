# PyPI trusted publishing (one-time setup)

`lime-sites-sdk` publishes via GitHub → PyPI trusted publishing using
`.github/workflows/publish.yml`. The one-time publisher registration on PyPI is
done; this document is kept as the reference for the exact field values.

## Configure on PyPI

1. Log in at https://pypi.org
2. Open **lime-sites-sdk** → **Manage** → **Publishing**
3. Add **GitHub** trusted publisher:

| Field | Value |
|-------|-------|
| PyPI project name | `lime-sites-sdk` |
| Owner | `Mawyxx` |
| Repository name | `lime-site-sdk` ← **без `s` в site** |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

4. Push a new tag (`v*`) → the **Publish** workflow runs and uploads via OIDC.

## OIDC claims (must match PyPI publisher exactly)

GitHub sends these claims on publish:

```
repository:     Mawyxx/lime-site-sdk
workflow:       publish.yml
environment:    pypi
ref:            refs/tags/v2.0.5
```

**Common mistakes:**

| Mistake | Correct |
|---------|---------|
| GitHub repo `lime-sites-sdk` | `lime-site-sdk` (no **s** in site) |
| PyPI project `lime-site-sdk` | `lime-sites-sdk` (with **s** in sites) |
| Workflow `Publish` or `ci.yml` | `publish.yml` |
| Environment left empty | `pypi` |

## No token fallback

The API-token fallback was removed in 2.0.5: `publish-token.yml` is deleted and
`PYPI_API_TOKEN` is revoked. If publishing fails with `invalid-publisher`, fix
the publisher fields above — do not reintroduce a long-lived token.

## Verify

```bash
pip index versions lime-sites-sdk
# expect 2.0.5
```
