"""Pytest configuration for lime-sites-sdk."""

from __future__ import annotations

import os

import pytest

from lime_sites._jwks import clear_jwks_cache


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live HTTP tests against LIME API (requires LIME_INTEGRATION=1)",
    )


@pytest.fixture(autouse=True)
def _reset_jwks_cache() -> None:
    clear_jwks_cache()
    yield
    clear_jwks_cache()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("LIME_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="Set LIME_INTEGRATION=1 to run live API tests")
    for item in items:
        if "integration" in item.nodeid.replace("\\", "/"):
            item.add_marker(skip)
