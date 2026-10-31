"""Tests for vehicle artwork discovery."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.mynissan.const import DOMAIN

from .test_init import VEHICLE, VEHICLE_CAPABILITIES, VEHICLE_LOCATION, VEHICLE_STATUS, _entry


@pytest.mark.parametrize("url", [None, "", "https://example.com/vehicle.png"])
async def test_vehicle_image(hass: HomeAssistant, url: str | None) -> None:
    """Only supplied artwork creates an image entity on the vehicle's device."""
    entry = _entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_vehicles = AsyncMock(
        return_value=(replace(VEHICLE, image_url=url, color="KAD"),)
    )
    client.async_get_vehicle_capabilities = AsyncMock(return_value=VEHICLE_CAPABILITIES)
    client.async_get_vehicle_status = AsyncMock(return_value=VEHICLE_STATUS)
    client.async_get_vehicle_location = AsyncMock(return_value=VEHICLE_LOCATION)
    with patch("custom_components.mynissan.create_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    registry = er.async_get(hass)
    tracker_id = registry.async_get_entity_id(
        Platform.DEVICE_TRACKER, DOMAIN, f"{VEHICLE.vin}_location"
    )
    assert tracker_id is not None
    tracker_state = hass.states.get(tracker_id)
    assert tracker_state is not None
    assert tracker_state.attributes["color"] == "KAD"
    assert tracker_state.attributes.get("entity_picture") == (url or None)
    entity_id = registry.async_get_entity_id(Platform.IMAGE, DOMAIN, f"{VEHICLE.vin}_vehicle")
    if not url:
        assert entity_id is None
        return
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state not in ("unknown", "unavailable")
    assert state.attributes["entity_picture"].startswith("/api/image_proxy/")
    image_entry = registry.async_get(entity_id)
    battery_id = registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{VEHICLE.vin}_battery_level"
    )
    assert image_entry is not None and battery_id is not None
    battery_entry = registry.async_get(battery_id)
    assert battery_entry is not None
    assert image_entry.device_id == battery_entry.device_id
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
