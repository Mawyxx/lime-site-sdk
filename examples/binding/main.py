"""Sketch: create binding request (exchange + verify on your redirect callback)."""

from __future__ import annotations

import asyncio

from lime_sites import LimeSite


async def main() -> None:
    site = LimeSite()
    req = await site.create_binding_request(
        redirect_uri="https://yoursite.example/bind/callback",
    )
    print("binding_id:", req.binding_id)
    print("connect_url:", req.connect_url)
    # Persist binding_id ↔ user_id, redirect browser to connect_url.
    # Callback: ?binding_code= (not JWT).
    # POST /api/v1/modules/bindings/exchange with X-Site-Token → passport
    # Then: await site.verify_binding_passport(passport)
    # → claims["binding_id"] / claims["agent_id"]
    await site.aclose()


if __name__ == "__main__":
    asyncio.run(main())
