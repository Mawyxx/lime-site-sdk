# Agent binding (Connect)

```bash
pip install lime-sites-sdk
export LIME_SITE_TOKEN=st_...
python main.py
```

**IS → DO**

1. Persist `binding_id` before redirecting the human to `connect_url`.
2. Callback carries `?binding_code=` (not a JWT).
3. `POST /api/v1/modules/bindings/exchange` with Site Token → passport.
4. `verify_binding_passport(passport)` locally via Core JWKS.

Guide: https://lime.pics/docs/guides/site-binding/
