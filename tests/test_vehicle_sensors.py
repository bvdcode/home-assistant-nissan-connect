"""Tests for vehicle charging, mileage, pressure and warnings."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_conversion import PressureConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pynissan import (
    DistanceReading,
    DistanceUnit,
    EngineOilDrainRange,
    MaintenanceIndicator,
    Mileage,
    TirePressure,
    VehicleCapabilities,
    VehicleStatus,
)

from custom_components.mynissan.charge_completion import remaining_charge_minutes
from custom_components.mynissan.const import DOMAIN
from custom_components.mynissan.coordinator import NissanVehicleData

from .test_init import (
    VEHICLE,
    VEHICLE_CAPABILITIES,
    VEHICLE_LOCATION,
    VEHICLE_STATUS,
    _entity_state,
    _entry,
)


async def setup_vehicle(
    hass: HomeAssistant,
    status: VehicleStatus,
    *,
    capabilities: VehicleCapabilities = VEHICLE_CAPABILITIES,
) -> MagicMock:
    """Load one vehicle using cached SDK data."""
    entry = _entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_vehicles = AsyncMock(return_value=(VEHICLE,))
    client.async_get_vehicle_capabilities = AsyncMock(return_value=capabilities)
    client.async_get_vehicle_status = AsyncMock(return_value=status)
    client.async_get_vehicle_location = AsyncMock(return_value=VEHICLE_LOCATION)
    with patch("custom_components.mynissan.create_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    client.coordinator = entry.runtime_data.coordinator
    return client


async def test_extended_sensors(hass: HomeAssistant) -> None:
    """Sensors retain native units, individual wheels, and active messages."""
    assert VEHICLE_STATUS.battery is not None
    status = replace(
        VEHICLE_STATUS,
        battery=replace(VEHICLE_STATUS.battery, is_charging=True),
        mileage=Mileage(12345, "KILOMETER", None),
        tire_pressure=TirePressure(None, 35, 36, 37, 38, 0, 1, 2, None),
        maintenance_indicators=(
            MaintenanceIndicator(True, "Check tire pressure", "TIRE_PRESSURE"),
            MaintenanceIndicator(False, "Inactive message", "OTHER"),
            MaintenanceIndicator(None, "Unknown state", "UNKNOWN"),
            MaintenanceIndicator(True, None, "SERVICE"),
        ),
    )
    client = await setup_vehicle(hass, status)
    fetched_at = datetime(2026, 10, 30, 12, tzinfo=UTC)
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(status, VEHICLE_LOCATION, fetched_at)}
    )
    assert _entity_state(hass, Platform.SENSOR, "odometer").state == "12345"
    assert _entity_state(hass, Platform.SENSOR, "remaining_charge_time").state == "42"
    completion = _entity_state(hass, Platform.SENSOR, "charge_completion")
    assert completion.state == (fetched_at + timedelta(minutes=42)).isoformat()
    assert NissanVehicleData(status, VEHICLE_LOCATION, fetched_at) != NissanVehicleData(
        status, VEHICLE_LOCATION, fetched_at + timedelta(minutes=15)
    )
    for position, value, tire_status in (
        ("front_left", 35, 0),
        ("front_right", 36, 1),
        ("rear_left", 37, 2),
        ("rear_right", 38, None),
    ):
        state = _entity_state(hass, Platform.SENSOR, f"tire_pressure_{position}")
        assert float(state.state) == pytest.approx(PressureConverter.convert(value, "psi", "kPa"))
        assert state.attributes["unit_of_measurement"] == "kPa"
        assert state.attributes["status"] == tire_status
    warnings = _entity_state(hass, Platform.SENSOR, "warnings")
    assert warnings.state == "2"
    assert warnings.attributes["warnings"] == [
        {"type": "TIRE_PRESSURE", "message": "Check tire pressure"},
        {"type": "SERVICE", "message": None},
    ]
    assert status.battery is not None
    stopped = replace(status, battery=replace(status.battery, is_charging=False))
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(stopped, VEHICLE_LOCATION)}
    )
    assert _entity_state(hass, Platform.SENSOR, "charge_completion").state == "unknown"
    assert _entity_state(hass, Platform.SENSOR, "remaining_charge_time").state == "42"
    client.async_get_vehicle_status.assert_awaited_once()
    client.async_get_vehicle_location.assert_awaited_once()


@pytest.mark.parametrize(
    ("charging", "minutes", "expected"),
    [(True, 0, 0), (True, -1, None), (True, None, None), (False, 42, 42), (None, 42, 42)],
)
def test_charging_duration(
    charging: bool | None, minutes: int | None, expected: int | None
) -> None:
    """Valid reported durations remain available even outside an active charge."""
    assert VEHICLE_STATUS.battery is not None
    status = replace(
        VEHICLE_STATUS,
        battery=replace(
            VEHICLE_STATUS.battery, is_charging=charging, remaining_charge_time=minutes
        ),
    )
    assert remaining_charge_minutes(status) == expected
    assert remaining_charge_minutes(replace(status, battery=None)) is None


async def test_missing_readings_and_recovery(hass: HomeAssistant) -> None:
    """Missing values remain unknown and recover when data becomes available."""
    status = replace(
        VEHICLE_STATUS,
        mileage=Mileage(None, "MILE", None),
        tire_pressure=TirePressure(None, None, 35, None, 36, None, None, None, None),
    )
    client = await setup_vehicle(hass, status)
    assert _entity_state(hass, Platform.SENSOR, "odometer").state == "unavailable"
    assert _entity_state(hass, Platform.SENSOR, "tire_pressure_front_left").state == "unavailable"
    assert _entity_state(hass, Platform.SENSOR, "warnings").state == "0"
    updated = replace(status, mileage=Mileage(100, "MILE", None))
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(updated, VEHICLE_LOCATION)}
    )
    odometer = _entity_state(hass, Platform.SENSOR, "odometer")
    assert float(odometer.state) == pytest.approx(160.9344)
    assert odometer.attributes["unit_of_measurement"] == "km"


async def test_fuel_and_oil_change_range(hass: HomeAssistant) -> None:
    """Gasoline vehicles report fuel range and distance until the next oil change."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    reported_at = datetime(2026, 11, 2, 3, 6, 5, tzinfo=UTC)
    status = replace(
        VEHICLE_STATUS,
        battery=None,
        climate=None,
        fuel_range=DistanceReading(345, "MILE", reported_at),
        engine_oil_drain_range=EngineOilDrainRange(9700, DistanceUnit.MILE, reported_at),
    )
    client = await setup_vehicle(hass, status)
    fuel = _entity_state(hass, Platform.SENSOR, "fuel_range")
    assert float(fuel.state) == 345
    assert fuel.attributes["unit_of_measurement"] == "mi"
    oil = _entity_state(hass, Platform.SENSOR, "oil_change_range")
    assert float(oil.state) == 9700
    assert oil.attributes["unit_of_measurement"] == "mi"
    missing = replace(status, fuel_range=DistanceReading(None, "MILE", None))
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(missing, VEHICLE_LOCATION)}
    )
    assert _entity_state(hass, Platform.SENSOR, "fuel_range").state == "unavailable"


async def test_electric_vehicle_has_no_fuel_sensors(hass: HomeAssistant) -> None:
    """Vehicles that report no fuel or oil data get no sensors for them."""
    await setup_vehicle(hass, VEHICLE_STATUS)
    registry = er.async_get(hass)
    for key in ("fuel_range", "oil_change_range"):
        assert registry.async_get_entity_id(Platform.SENSOR, DOMAIN, f"{VEHICLE.vin}_{key}") is None


async def test_pressure_in_us_units(hass: HomeAssistant) -> None:
    """US units preserve SDK pressures in psi without converting them twice."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    status = replace(
        VEHICLE_STATUS,
        tire_pressure=TirePressure(None, 35, 36, 37, 38, 0, 0, 0, 0),
    )
    await setup_vehicle(hass, status)
    state = _entity_state(hass, Platform.SENSOR, "tire_pressure_front_left")
    assert float(state.state) == 35
    assert state.attributes["unit_of_measurement"] == "psi"
