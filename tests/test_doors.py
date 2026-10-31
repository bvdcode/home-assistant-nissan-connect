"""Tests for opening and lock status."""

from dataclasses import replace

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pynissan import DoorsStatus, DoorState

from custom_components.mynissan.coordinator import NissanVehicleData
from custom_components.mynissan.door_status import opening_state, unlocked_state

from .test_init import VEHICLE, VEHICLE_LOCATION, VEHICLE_STATUS, _entity_state
from .test_vehicle_sensors import setup_vehicle

DOORS = DoorsStatus(
    last_updated_at=None,
    front_left=DoorState("OPEN", None, "UNLOCKED"),
    front_right=DoorState("CLOSED", None, "LOCKED"),
    rear_left=DoorState("CLOSED", None, "UNLOCKED"),
    rear_right=DoorState("OPEN", None, "LOCKED"),
    engine_hood_ajar="OPEN",
    hatch_ajar="CLOSED",
    sunroof_ajar=None,
    trunk_lock="LOCKED",
    overall_lock="UNLOCKED",
)


async def test_openings_and_locks(hass: HomeAssistant) -> None:
    """Each opening and lock retains its own state without a battery dependency."""
    status = replace(VEHICLE_STATUS, battery=None, doors=DOORS)
    client = await setup_vehicle(hass, status)
    for key, expected in (
        ("door_front_left", "on"),
        ("door_front_right", "off"),
        ("door_rear_left", "off"),
        ("door_rear_right", "on"),
        ("door_front_left_unlocked", "on"),
        ("door_front_right_unlocked", "off"),
        ("door_rear_left_unlocked", "on"),
        ("door_rear_right_unlocked", "off"),
        ("hood", "on"),
        ("hatch", "off"),
        ("trunk_unlocked", "off"),
        ("doors_unlocked", "on"),
    ):
        assert _entity_state(hass, Platform.BINARY_SENSOR, key).state == expected
    unknown = replace(status, doors=replace(DOORS, front_left=None, overall_lock="UNKNOWN__"))
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(unknown, VEHICLE_LOCATION)}
    )
    assert _entity_state(hass, Platform.BINARY_SENSOR, "doors_unlocked").state == "unavailable"
    assert _entity_state(hass, Platform.BINARY_SENSOR, "door_front_left").state == "unavailable"


@pytest.mark.parametrize("value", [None, "UNKNOWN__", "UNRECOGNIZED"])
def test_unknown_states(value: str | None) -> None:
    """Unknown values must never imply a secure vehicle."""
    assert opening_state(value) is None
    assert unlocked_state(value) is None
