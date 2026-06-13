from __future__ import annotations

import pytest

from lime_sites._types import LoginResult


def test_login_result_from_sse_with_redirect() -> None:
    result = LoginResult.from_sse(
        {
            "type": "approved",
            "login_request_id": "lr_1",
            "agent_passport_jwt": "jwt.token",
            "redirect_url": "https://site.example/callback",
        },
    )
    assert result.request_id == "lr_1"
    assert result.agent_passport_jwt == "jwt.token"
    assert result.redirect_url == "https://site.example/callback"


def test_login_result_from_sse_missing_jwt() -> None:
    with pytest.raises(ValueError, match="agent_passport_jwt"):
        LoginResult.from_sse(
            {
                "type": "approved",
                "login_request_id": "lr_1",
            },
        )
