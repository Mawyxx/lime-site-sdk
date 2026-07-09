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
| Repository name | `lime-site-sdk` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

4. Re-run the failed **Publish** workflow for tag `v1.1.0`, or push a new tag.

## Verify

```bash
pip index versions lime-sites-sdk
# expect 1.1.0
```
