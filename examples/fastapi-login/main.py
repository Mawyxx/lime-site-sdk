"""Canonical FastAPI + LimeSite login pattern."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from lime_sites import InvalidPassportError, LimeSite

pending_logins: dict[str, object] = {}
site: LimeSite


@asynccontextmanager
async def lifespan(app: FastAPI):
    global site
    site = LimeSite()

    @site.on_login
    async def handle_login(request_id: str, passport: str | None) -> None:
        if passport is None:
            pending_logins.pop(request_id, None)
            return
        try:
            verified = await site.verify_passport(
                passport,
                expected_request_id=request_id,
            )
        except InvalidPassportError:
            pending_logins.pop(request_id, None)
            return
        pending_logins[request_id] = verified.claims

    yield
    await site.aclose()


app = FastAPI(lifespan=lifespan)


@app.post("/login/start")
async def start_login() -> dict[str, str]:
    req = await site.create_login_request()
    return {"request_id": req.request_id}
