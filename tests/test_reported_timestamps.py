"""Tests for observation times supplied with cached vehicle readings."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pynissan import Mileage, TirePressure

from custom_components.mynissan.binary_sensor import DOOR_SENSOR_DESCRIPTIONS
from custom_components.mynissan.coordinator import NissanVehicleData

from .test_commands import setup_commands
from .test_doors import DOORS
from .test_init import VEHICLE, VEHICLE_LOCATION, VEHICLE_STATUS, _entity_state
from .test_vehicle_sensors import setup_vehicle

MILEAGE_TIME = datetime(2026, 10, 30, 12, tzinfo=UTC)
TIRE_TIME = datetime(2026, 10, 30, 10, tzinfo=timezone(timedelta(hours=-7)))
DOOR_TIME = datetime(2026, 10, 30, 14, tzinfo=timezone(timedelta(hours=5, minutes=30)))


async def test_reported_timestamps(hass: HomeAssistant) -> None:
    """Each reading retains its source time, updates independently, and clears it."""
    status = replace(
        VEHICLE_STATUS,
        mileage=Mileage(12345, "KILOMETER", MILEAGE_TIME),
        tire_pressure=TirePressure(TIRE_TIME, 35, 36, 37, 38, 0, 1, 2, 3),
        doors=replace(DOORS, last_updated_at=DOOR_TIME),
    )
    client = await setup_vehicle(hass, status)
    readings = (
        (Platform.SENSOR, "odometer", MILEAGE_TIME),
        *(
            (Platform.SENSOR, f"tire_pressure_{position}", TIRE_TIME)
            for position in ("front_left", "front_right", "rear_left", "rear_right")
        ),
        *(
            (Platform.BINARY_SENSOR, description.key, DOOR_TIME)
            for description in DOOR_SENSOR_DESCRIPTIONS
        ),
    )
    for platform, key, timestamp in readings:
        assert _entity_state(hass, platform, key).attributes["last_updated_at"] == (
            timestamp.isoformat()
        )
    assert (
        _entity_state(hass, Platform.SENSOR, "tire_pressure_front_right").attributes["status"] == 1
    )
    for platform, key in (
        (Platform.SENSOR, "battery_level"),
        (Platform.SENSOR, "warnings"),
        (Platform.BINARY_SENSOR, "charging"),
    ):
        assert "last_updated_at" not in _entity_state(hass, platform, key).attributes

    assert status.mileage is not None and status.tire_pressure is not None
    updated = replace(
        status,
        mileage=replace(status.mileage, recorded_at=MILEAGE_TIME + timedelta(minutes=15)),
        tire_pressure=replace(status.tire_pressure, last_updated_at=None),
        doors=replace(DOORS, last_updated_at=None),
    )
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(updated, VEHICLE_LOCATION)}
    )
    odometer = _entity_state(hass, Platform.SENSOR, "odometer")
    assert odometer.state == "12345"
    assert (
        odometer.attributes["last_updated_at"] == (MILEAGE_TIME + timedelta(minutes=15)).isoformat()
    )
    for platform, key, _timestamp in readings[1:]:
        assert "last_updated_at" not in _entity_state(hass, platform, key).attributes

    missing = replace(status, mileage=None, tire_pressure=None, doors=None)
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(missing, VEHICLE_LOCATION)}
    )
    for platform, key, _timestamp in readings:
        state = _entity_state(hass, platform, key)
        assert state.state == "unavailable"
        assert "last_updated_at" not in state.attributes
    client.async_get_vehicle_status.assert_awaited_once()
    client.async_get_vehicle_location.assert_awaited_once()


async def test_lock_reported_timestamp(hass: HomeAssistant) -> None:
    """The remote lock displays the reported observation time without a command."""
    client = await setup_commands(hass)
    state = _entity_state(hass, Platform.LOCK, "door_lock")
    assert "last_updated_at" not in state.attributes
    for doors, expected in (
        (replace(DOORS, last_updated_at=DOOR_TIME), DOOR_TIME.isoformat()),
        (replace(DOORS, last_updated_at=None), None),
        (None, None),
    ):
        status = replace(VEHICLE_STATUS, doors=doors)
        client.coordinator.async_set_updated_data(
            {VEHICLE.vin: NissanVehicleData(status, VEHICLE_LOCATION)}
        )
        state = _entity_state(hass, Platform.LOCK, "door_lock")
        assert state.attributes.get("last_updated_at") == expected
    client.async_lock_doors.assert_not_called()
    client.async_unlock_doors.assert_not_called()
