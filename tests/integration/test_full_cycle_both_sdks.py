"""Live integration: lime-sites-sdk + lime-agents-sdk full cycle against production."""

from __future__ import annotations

import asyncio
import os

import pytest

from lime_agents import LimeAgent
from lime_sites import LimeSite, RequestExpiredError, TimeoutError

from .bootstrap import DEFAULT_BASE_URL, ensure_tokens

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("LIME_API_BASE", DEFAULT_BASE_URL).rstrip("/")
INVALID_REQUEST_ID = "00000000-0000-4000-8000-000000000099"
SSE_WAIT_TIMEOUT = 310.0


@pytest.fixture
async def tokens() -> tuple[str, str]:
    return await ensure_tokens(BASE_URL)


@pytest.mark.asyncio
async def test_full_cycle_both_sdks(tokens: tuple[str, str]) -> None:
    """Site create → SSE listen → agent approve → passport verify → agent profile."""
    agent_token, site_token = tokens

    async with LimeSite(site_token=site_token, base_url=BASE_URL) as site:
        req = await site.create_login_request()
        assert req.status == "PENDING"
        request_id = req.request_id
        print(f"[Site] Created request: {request_id}")

        wait_task = asyncio.create_task(
            site.wait_for_login(request_id, timeout=SSE_WAIT_TIMEOUT),
            name="site_wait_for_login",
        )

        async with LimeAgent(agent_token=agent_token, base_url=BASE_URL) as agent:
            result = await agent.approve(request_id)
            assert result.status in ("APPROVED", "DELIVERED")
            print(f"[Agent] Approved: {result.status}")

            login = await wait_task
            assert login.agent_passport_jwt is not None
            print(f"[Site] Received passport for {login.request_id}")

            verified = await site.verify_passport(
                login.agent_passport_jwt,
                expected_request_id=request_id,
            )
            assert verified.valid
            assert verified.claims["request_id"] == request_id
            agent_id = verified.claims.get("agent_id") or verified.claims.get("sub")
            print(f"[Site] Passport verified: agent_id={agent_id}")

            profile = await agent.get_profile()
            assert profile.agent_id is not None
            print(f"[Agent] Profile: {profile.display_name}")

    print("Full cycle test passed: site → agent → passport → verify → profile")


@pytest.mark.asyncio
async def test_wait_for_login_invalid_request_id_raises(tokens: tuple[str, str]) -> None:
    """Unknown request_id must not return a passport (timeout or expired)."""
    _, site_token = tokens

    async with LimeSite(site_token=site_token, base_url=BASE_URL) as site:
        with pytest.raises((TimeoutError, RequestExpiredError)) as exc_info:
            await site.wait_for_login(INVALID_REQUEST_ID, timeout=10.0)

    err = exc_info.value
    print(f"[Site] Invalid request_id rejected: {type(err).__name__}: {err.message}")
