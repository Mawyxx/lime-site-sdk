from __future__ import annotations

import pytest

from lime_sites._errors import ApiError
from lime_sites._sse import (
    SseFrameKind,
    classify_sse_payload,
    iter_sse_data_payloads,
    parse_sse_json_payload,
)


def test_parse_sse_json_payload_valid() -> None:
    payload = parse_sse_json_payload('{"type":"keepalive"}')
    assert payload["type"] == "keepalive"


def test_parse_sse_json_payload_invalid_json() -> None:
    with pytest.raises(ApiError, match="Invalid SSE"):
        parse_sse_json_payload("not-json")


def test_parse_sse_json_payload_non_object() -> None:
    with pytest.raises(ApiError, match="JSON object"):
        parse_sse_json_payload("[]")


def test_classify_keepalive() -> None:
    event = classify_sse_payload({"type": "keepalive"})
    assert event.kind == SseFrameKind.KEEPALIVE


def test_classify_approved() -> None:
    event = classify_sse_payload(
        {
            "type": "approved",
            "login_request_id": "lr_1",
            "agent_passport_jwt": "jwt.token",
        },
    )
    assert event.kind == SseFrameKind.APPROVED
    assert event.request_id == "lr_1"
    assert event.passport == "jwt.token"


def test_classify_expired() -> None:
    event = classify_sse_payload(
        {
            "type": "expired",
            "login_request_id": "lr_1",
        },
    )
    assert event.kind == SseFrameKind.EXPIRED
    assert event.request_id == "lr_1"
    assert event.passport is None


def test_classify_error() -> None:
    event = classify_sse_payload(
        {
            "type": "error",
            "code": "SSE_ERR",
            "message": "boom",
        },
    )
    assert event.kind == SseFrameKind.ERROR
    assert event.error_code == "SSE_ERR"


def test_classify_approved_missing_jwt() -> None:
    with pytest.raises(ApiError, match="agent_passport_jwt"):
        classify_sse_payload(
            {
                "type": "approved",
                "login_request_id": "lr_1",
            },
        )


def test_classify_unknown_type() -> None:
    event = classify_sse_payload({"type": "challenge", "login_request_id": "lr_1"})
    assert event.kind == SseFrameKind.IGNORE


def test_classify_missing_request_id() -> None:
    event = classify_sse_payload({"type": "expired"})
    assert event.kind == SseFrameKind.IGNORE


def test_iter_sse_data_payloads() -> None:
    buffer, payloads = iter_sse_data_payloads("", "data: {\"a\":1}\n\n")
    assert payloads == ["{\"a\":1}"]
    assert buffer == ""

    buffer, payloads = iter_sse_data_payloads("", "data: partial")
    assert payloads == []

    buffer, payloads = iter_sse_data_payloads(buffer, "\n\n")
    assert payloads == ["partial"]
    assert buffer == ""


def test_iter_sse_skips_empty_data() -> None:
    buffer, payloads = iter_sse_data_payloads("", "data:\n\n")
    assert payloads == []

