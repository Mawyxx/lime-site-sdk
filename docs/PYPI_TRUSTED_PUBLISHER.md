# PyPI trusted publishing (one-time setup)

`lime-mcp-server-sdk` already uses GitHub → PyPI trusted publishing via `.github/workflows/publish.yml`.
`lime-sites-sdk` needs the same publisher registered on PyPI **once**.

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

4. Re-run the failed **Publish** workflow for tag `v1.1.0`, or push a new tag.

## OIDC claims (must match PyPI publisher exactly)

GitHub sends these claims on publish:

```
repository:     Mawyxx/lime-site-sdk
workflow:       publish.yml
environment:    pypi
ref:            refs/tags/v1.1.0
```

**Common mistakes:**

| Mistake | Correct |
|---------|---------|
| GitHub repo `lime-sites-sdk` | `lime-site-sdk` (no **s** in site) |
| PyPI project `lime-site-sdk` | `lime-sites-sdk` (with **s** in sites) |
| Workflow `Publish` or `ci.yml` | `publish.yml` |
| Environment left empty | `pypi` |

## Fallback: API token

If trusted publishing still fails, set a repo secret and run **Publish (API token)** workflow:

```bash
gh secret set PYPI_API_TOKEN --repo Mawyxx/lime-site-sdk
gh workflow run "Publish (API token)" --repo Mawyxx/lime-site-sdk
```

Token: PyPI → Account settings → API tokens → scope `lime-sites-sdk`.

## Verify

```bash
pip index versions lime-sites-sdk
# expect 1.1.0
```
