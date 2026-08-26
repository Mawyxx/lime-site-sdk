"""End-to-end sketch: site creates login, agent approves, site verifies passport."""

from __future__ import annotations

import asyncio

from lime_agents import LimeAgent
from lime_sites import LimeSite


async def main() -> None:
    received = asyncio.Event()
    box: dict[str, str] = {}

    site = LimeSite()

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        if passport:
            box["jwt"] = passport
            received.set()

    req = await site.create_login_request()
    print("request_id:", req.request_id)

    async with LimeAgent() as agent:
        await agent.login(req.request_id)

    await asyncio.wait_for(received.wait(), timeout=120)
    verified = await site.verify_passport(box["jwt"], expected_request_id=req.request_id)
    print(verified.claims)
    await site.aclose()


if __name__ == "__main__":
    asyncio.run(main())
