"""Shared fixtures for MyNISSAN tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable custom integrations for every test."""
    del enable_custom_integrations


@pytest.fixture
def mock_nissan_client() -> Generator[MagicMock]:
    """Replace the SDK client constructor with a configured mock."""
    with patch("custom_components.mynissan.api.NissanClient") as client_class:
        client = client_class.return_value
        client.async_authenticate = AsyncMock()
        client.async_get_vehicles = AsyncMock()
        client.oauth_device_id = "oauth-device-id"
        yield client
