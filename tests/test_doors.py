"""Tests for opening and lock status."""

from dataclasses import replace

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pynissan import AccessoryCapability, DoorsStatus, DoorState, SunRoofCapability

from custom_components.mynissan.const import DOMAIN
from custom_components.mynissan.coordinator import NissanVehicleData
from custom_components.mynissan.door_status import opening_state, unlocked_state, window_state

from .test_init import (
    VEHICLE,
    VEHICLE_CAPABILITIES,
    VEHICLE_LOCATION,
    VEHICLE_STATUS,
    _entity_state,
)
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


async def test_windows_and_sunroof(hass: HomeAssistant) -> None:
    """Reported windows and the sunroof each get a sensor; unreported ones get none."""
    doors = replace(
        DOORS,
        front_left=DoorState("CLOSED", "OPEN", "LOCKED"),
        front_right=DoorState("CLOSED", "CLOSED", "LOCKED"),
        rear_left=DoorState("CLOSED", "PARTIALLY_OPEN", "LOCKED"),
        rear_right=DoorState("CLOSED", None, "LOCKED"),
        sunroof_ajar="CLOSED",
    )
    await setup_vehicle(hass, replace(VEHICLE_STATUS, battery=None, doors=doors))
    for key, expected in (
        ("window_front_left", "on"),
        ("window_front_right", "off"),
        ("window_rear_left", "on"),
        ("sunroof", "off"),
    ):
        assert _entity_state(hass, Platform.BINARY_SENSOR, key).state == expected
    assert (
        er.async_get(hass).async_get_entity_id(
            Platform.BINARY_SENSOR, DOMAIN, f"{VEHICLE.vin}_window_rear_right"
        )
        is None
    )


async def test_no_window_sensors_without_window_data(hass: HomeAssistant) -> None:
    """Vehicles that never report windows get no window sensors."""
    await setup_vehicle(hass, replace(VEHICLE_STATUS, battery=None, doors=DOORS))
    for key in ("window_front_left", "window_front_right", "window_rear_left", "sunroof"):
        assert (
            er.async_get(hass).async_get_entity_id(
                Platform.BINARY_SENSOR, DOMAIN, f"{VEHICLE.vin}_{key}"
            )
            is None
        )


@pytest.mark.parametrize("initial_doors", [None, DOORS])
async def test_supported_windows_recover_from_missing_initial_readings(
    hass: HomeAssistant, initial_doors: DoorsStatus | None
) -> None:
    """Advertised windows and sunroof become available when their first readings arrive."""
    assert VEHICLE_CAPABILITIES.accessories_details is not None
    capabilities = replace(
        VEHICLE_CAPABILITIES,
        accessories_details=replace(
            VEHICLE_CAPABILITIES.accessories_details,
            window_status=AccessoryCapability(True),
            sun_roof=SunRoofCapability(None, True),
        ),
    )
    client = await setup_vehicle(
        hass,
        replace(VEHICLE_STATUS, battery=None, doors=initial_doors),
        capabilities=capabilities,
    )
    states = (
        ("window_front_left", "on"),
        ("window_front_right", "off"),
        ("window_rear_left", "on"),
        ("window_rear_right", "off"),
        ("sunroof", "on"),
    )
    for key, _ in states:
        assert _entity_state(hass, Platform.BINARY_SENSOR, key).state == "unavailable"
    known = replace(
        VEHICLE_STATUS,
        battery=None,
        doors=replace(
            DOORS,
            front_left=DoorState("CLOSED", "OPEN", "LOCKED"),
            front_right=DoorState("CLOSED", "CLOSED", "LOCKED"),
            rear_left=DoorState("CLOSED", "PARTIALLY_OPEN", "LOCKED"),
            rear_right=DoorState("CLOSED", "CLOSED", "LOCKED"),
            sunroof_ajar="OPEN",
        ),
    )
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(known, VEHICLE_LOCATION)}
    )
    for key, expected in states:
        assert _entity_state(hass, Platform.BINARY_SENSOR, key).state == expected


@pytest.mark.parametrize("value", [None, "UNKNOWN__", "UNRECOGNIZED"])
def test_unknown_states(value: str | None) -> None:
    """Unknown values must never imply a secure vehicle."""
    assert opening_state(value) is None
    assert unlocked_state(value) is None
    assert window_state(value) is None
