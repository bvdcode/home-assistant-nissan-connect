"""Tests for MyNISSAN config entry setup."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from pynissan import AuthenticationError, NetworkError, NissanError, Tokens, Vehicle
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mynissan import async_setup_entry
from custom_components.mynissan.const import (
    CONF_COUNTRY,
    CONF_OAUTH_DEVICE_ID,
    CONF_TOKENS,
    DOMAIN,
)

VEHICLE = Vehicle("JN1TESTVIN0000001", "2025", "ARIYA", None, "Family Ariya", None, None, None)


async def test_setup_registers_vehicle_and_persists_refreshed_tokens(
    hass: HomeAssistant,
) -> None:
    """Setup creates runtime data, a device, and a working token listener."""
    entry = _entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_vehicles = AsyncMock(return_value=(VEHICLE,))
    token_listener: Callable[[Tokens], None] | None = None

    def create_client(_hass: HomeAssistant, **kwargs: object) -> MagicMock:
        nonlocal token_listener
        token_listener = kwargs["token_listener"]  # type: ignore[assignment]
        return client

    with patch(
        "custom_components.mynissan.create_client",
        side_effect=create_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.client is client
    assert entry.runtime_data.vehicles == (VEHICLE,)

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, VEHICLE.vin)})
    assert device is not None
    assert device.name == "Family Ariya"
    assert device.manufacturer == "Nissan"
    assert device.model == "ARIYA"
    assert device.serial_number == VEHICLE.vin

    assert token_listener is not None
    token_listener(Tokens("new-access", "new-refresh", "new-id"))
    assert entry.data[CONF_TOKENS] == {
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "id_token": "new-id",
    }


@pytest.mark.parametrize(
    ("error", "expected_exception"),
    [
        (AuthenticationError(401, "Unauthorized"), ConfigEntryAuthFailed),
        (NetworkError(), ConfigEntryNotReady),
        (NissanError(), ConfigEntryError),
    ],
)
async def test_setup_translates_client_errors(
    hass: HomeAssistant,
    error: NissanError,
    expected_exception: type[Exception],
) -> None:
    """Setup translates SDK failures to Home Assistant entry errors."""
    entry = _entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_vehicles = AsyncMock(side_effect=error)

    with (
        patch("custom_components.mynissan.create_client", return_value=client),
        pytest.raises(expected_exception),
    ):
        await async_setup_entry(hass, entry)  # type: ignore[arg-type]


async def test_setup_rejects_account_without_vehicles(hass: HomeAssistant) -> None:
    """Setup fails clearly when the account no longer contains vehicles."""
    entry = _entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_vehicles = AsyncMock(return_value=())

    with (
        patch("custom_components.mynissan.create_client", return_value=client),
        pytest.raises(ConfigEntryError),
    ):
        await async_setup_entry(hass, entry)  # type: ignore[arg-type]


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="US:driver@example.com",
        title="driver@example.com",
        data={
            CONF_COUNTRY: "US",
            CONF_EMAIL: "driver@example.com",
            CONF_OAUTH_DEVICE_ID: "oauth-device-id",
            CONF_TOKENS: {
                "access_token": "access",
                "refresh_token": "refresh",
                "id_token": "id",
            },
        },
    )
