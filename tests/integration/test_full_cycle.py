"""Live integration: site SDK create/wait/verify + lime-agents-sdk approve."""

from __future__ import annotations

import asyncio
import os

import pytest

from lime_sites import LimeSite

from .bootstrap import DEFAULT_BASE_URL, ensure_tokens

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("LIME_API_BASE", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture
async def tokens() -> tuple[str, str]:
    return await ensure_tokens(BASE_URL)


@pytest.fixture
async def site_token(tokens: tuple[str, str]) -> str:
    return tokens[1]


@pytest.fixture
async def agent_token(tokens: tuple[str, str]) -> str:
    return tokens[0]


@pytest.mark.asyncio
async def test_full_cycle_create_wait_verify(site_token: str, agent_token: str) -> None:
    lime_agents = pytest.importorskip("lime_agents")
    LimeAgent = lime_agents.LimeAgent

    async with LimeSite(site_token=site_token, base_url=BASE_URL) as site:
        req = await site.create_login_request()
        assert req.request_id.strip()
        assert req.status == "PENDING"

        async def approve_in_background() -> None:
            await asyncio.sleep(0.5)
            async with LimeAgent(agent_token=agent_token, base_url=BASE_URL) as agent:
                await agent.approve(req.request_id)

        approve_task = asyncio.create_task(approve_in_background())
        try:
            login = await site.wait_for_login(req.request_id, timeout=120.0)
            assert login.agent_passport_jwt.strip()

            verified = await site.verify_passport(
                login.agent_passport_jwt,
                expected_request_id=req.request_id,
            )
            assert verified.valid is True
            assert verified.claims.get("agent_id") or verified.claims.get("sub")
        finally:
            await approve_task
