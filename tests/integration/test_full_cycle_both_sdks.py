"""Live integration: lime-sites-sdk + lime-agents-sdk full cycle against production."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest
from lime_agents import LimeAgent

from lime_sites import LimeSite

from .bootstrap import DEFAULT_BASE_URL, ensure_tokens

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("LIME_API_BASE", DEFAULT_BASE_URL).rstrip("/")
SSE_WAIT_TIMEOUT = 310.0


@pytest.fixture
async def tokens() -> tuple[str, str]:
    return await ensure_tokens(BASE_URL)


@pytest.mark.asyncio
async def test_full_cycle_both_sdks(tokens: tuple[str, str]) -> None:
    """Site create → SSE dispatcher → agent approve → passport verify → agent profile."""
    agent_token, site_token = tokens
    received = asyncio.Event()
    box: dict[str, Any] = {}

    async with LimeSite(site_token=site_token, base_url=BASE_URL) as site:
        @site.on_login
        async def on_login(request_id: str, passport: str | None) -> None:
            box["request_id"] = request_id
            box["passport"] = passport
            received.set()

        req = await site.create_login_request()
        assert req.status == "PENDING"
        request_id = req.request_id
        print(f"[Site] Created request: {request_id}")

        async with LimeAgent(agent_token=agent_token, base_url=BASE_URL) as agent:
            result = await agent.approve(request_id)
            assert result.status in ("APPROVED", "DELIVERED")
            print(f"[Agent] Approved: {result.status}")

            await asyncio.wait_for(received.wait(), timeout=SSE_WAIT_TIMEOUT)
            assert box["passport"] is not None
            print(f"[Site] Received passport for {box['request_id']}")

            verified = await site.verify_passport(
                box["passport"],
                expected_request_id=request_id,
            )
            assert verified.valid is True
            print(f"[Site] Passport verified: agent_id={verified.claims.get('agent_id')}")

            profile = await agent.get_profile()
            assert profile.agent_id
            print(f"[Agent] Profile: {profile.agent_id}")

    print("Full cycle test passed: site → agent → passport → verify → profile")

