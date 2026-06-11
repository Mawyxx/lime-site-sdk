"""Provision or load integration tokens for live API tests."""

from __future__ import annotations

import os
from pathlib import Path

TOKENS_FILE = Path(__file__).with_name(".tokens.env")
DEFAULT_BASE_URL = "https://lime.pics/api/v1"

_PROD_VERIFY_SITE_TOKEN = "pow-prod-verify-site-token-v1"
_PROD_VERIFY_AGENT_TOKEN = "pow-prod-verify-agent-token-v1"


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def save_tokens(agent_token: str, site_token: str) -> None:
    TOKENS_FILE.write_text(
        f"LIME_AGENT_TOKEN={agent_token}\nLIME_SITE_TOKEN={site_token}\n",
        encoding="utf-8",
    )


def load_tokens_from_file() -> tuple[str, str] | None:
    if not TOKENS_FILE.exists():
        return None
    data = _parse_env_file(TOKENS_FILE)
    agent = data.get("LIME_AGENT_TOKEN", "").strip()
    site = data.get("LIME_SITE_TOKEN", "").strip()
    if agent and site:
        return agent, site
    return None


async def ensure_tokens(base_url: str) -> tuple[str, str]:
    """Resolve agent and site tokens from env, cache file, or prod fixtures."""
    agent = os.getenv("LIME_AGENT_TOKEN", "").strip()
    site = os.getenv("LIME_SITE_TOKEN", "").strip()
    if agent and site:
        return agent, site

    cached = load_tokens_from_file()
    if cached:
        return cached

    if "lime.pics" in base_url:
        tokens = (_PROD_VERIFY_AGENT_TOKEN, _PROD_VERIFY_SITE_TOKEN)
        save_tokens(*tokens)
        return tokens

    raise RuntimeError(
        "Set LIME_AGENT_TOKEN and LIME_SITE_TOKEN for integration tests",
    )
