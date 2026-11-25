"""Tests for the MyNISSAN data update coordinator."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pynissan import (
    AuthenticationError,
    BatteryStatus,
    DistanceReading,
    DistanceUnit,
    NetworkError,
    TemperatureUnit,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
)
from pytest_homeassistant.common import MockConfigEntry

from custom_components.mynissan.const import DOMAIN
from custom_components.mynissan.coordinator import (
    NissanDataUpdateCoordinator,
    NissanVehicleData,
)

VEHICLES = (
    Vehicle("VIN1", "2025", "ARIYA", None, "First", None, None, None),
    Vehicle("VIN2", "2024", "LEAF", None, "Second", None, None, None),
)


async def test_coordinator_fetches_every_vehicle(hass: HomeAssistant) -> None:
    """One coordinator update fetches cached status for every vehicle."""
    client = MagicMock()

    async def get_status(vin: str, **kwargs: object) -> VehicleStatus:
        assert kwargs == {
            "distance_unit": DistanceUnit.KILOMETER,
            "temperature_unit": TemperatureUnit.CELSIUS,
        }
        return _status(vin)

    client.async_get_vehicle_status = AsyncMock(side_effect=get_status)
    client.async_get_vehicle_location = AsyncMock(side_effect=_location)
    coordinator = NissanDataUpdateCoordinator(hass, _entry(), client, VEHICLES)

    data = await coordinator._async_update_data()

    assert data == {
        "VIN1": NissanVehicleData(_status("VIN1"), _location("VIN1"), data["VIN1"].received_at),
        "VIN2": NissanVehicleData(_status("VIN2"), _location("VIN2"), data["VIN2"].received_at),
    }
    assert client.async_get_vehicle_status.await_count == 2
    assert client.async_get_vehicle_location.await_count == 2


async def test_locate_restores_only_the_requested_vehicle(hass: HomeAssistant) -> None:
    """One successful locate restores only that vehicle's position during an outage."""
    client = MagicMock()
    client.async_get_vehicle_status = AsyncMock(side_effect=lambda vin, **kwargs: _status(vin))
    client.async_get_vehicle_location = AsyncMock(side_effect=_location)
    coordinator = NissanDataUpdateCoordinator(hass, _entry(), client, VEHICLES)
    await coordinator.async_refresh()
    coordinator.async_set_update_error(NetworkError())

    previous = coordinator.data["VIN1"].location
    result = replace(previous, last_updated_at=datetime(2026, 1, 2, tzinfo=UTC))
    assert coordinator.async_publish_vehicle_location(previous, result)
    assert coordinator.is_location_available("VIN1")
    assert not coordinator.is_location_available("VIN2")
    assert not coordinator.last_update_success


async def test_coordinator_requests_reauthentication(hass: HomeAssistant) -> None:
    """Authentication failures start Home Assistant's reauthentication flow."""
    client = MagicMock()
    client.async_get_vehicle_status = AsyncMock(
        side_effect=AuthenticationError(401, "Unauthorized")
    )
    client.async_get_vehicle_location = AsyncMock(return_value=_location("VIN1"))
    coordinator = NissanDataUpdateCoordinator(hass, _entry(), client, VEHICLES[:1])

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_translates_update_failure(hass: HomeAssistant) -> None:
    """Transient Nissan failures are exposed as coordinator update failures."""
    client = MagicMock()
    client.async_get_vehicle_status = AsyncMock(side_effect=NetworkError())
    client.async_get_vehicle_location = AsyncMock(return_value=_location("VIN1"))
    coordinator = NissanDataUpdateCoordinator(hass, _entry(), client, VEHICLES[:1])

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


def _entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, data={})


def _status(vin: str) -> VehicleStatus:
    return VehicleStatus(
        vin=vin,
        vehicle_type="ElectricAVK2Vehicle",
        battery=BatteryStatus(73, True, False, 42, DistanceReading(181, "KILOMETER")),
        climate=None,
        doors=None,
        fuel_range=None,
        mileage=None,
        tire_pressure=None,
        maintenance_indicators=(),
    )


def _location(vin: str) -> VehicleLocation:
    return VehicleLocation(vin, 32.7157, -117.1611, None)
