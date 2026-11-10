"""Tests for supported lock, light and horn commands."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pynissan import (
    ClimateParameters,
    ClimateSettings,
    NissanError,
    ServiceCapability,
    ServiceRequest,
    ServiceRequestKind,
    ServiceRequestResult,
    ServiceRequestStatus,
    TemperatureUnit,
)

from custom_components.mynissan.const import DOMAIN
from custom_components.mynissan.coordinator import NissanVehicleData

from .test_doors import DOORS
from .test_init import (
    VEHICLE,
    VEHICLE_CAPABILITIES,
    VEHICLE_LOCATION,
    VEHICLE_STATUS,
    _entity_state,
    _entry,
)

ALL_SERVICES = (
    ServiceCapability("REMOTE_DOOR_LOCK_UNLOCK", True, True),
    ServiceCapability("REMOTE_HORN_LIGHTS", True, True),
)


async def setup_commands(
    hass: HomeAssistant, services: tuple[ServiceCapability, ...] = ALL_SERVICES
) -> MagicMock:
    """Load command platforms with a fully mocked SDK client."""
    entry = _entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_vehicles = AsyncMock(return_value=(VEHICLE,))
    client.async_get_vehicle_capabilities = AsyncMock(
        return_value=replace(VEHICLE_CAPABILITIES, services=services)
    )
    client.async_get_vehicle_status = AsyncMock(return_value=replace(VEHICLE_STATUS, doors=DOORS))
    client.async_get_vehicle_location = AsyncMock(return_value=VEHICLE_LOCATION)
    client.async_get_climate_defaults = AsyncMock(return_value=None)
    client.async_lock_doors = AsyncMock(
        return_value=ServiceRequest("lock", ServiceRequestKind.DOOR)
    )
    client.async_unlock_doors = AsyncMock(
        return_value=ServiceRequest("unlock", ServiceRequestKind.DOOR)
    )
    client.async_flash_lights = AsyncMock(
        return_value=ServiceRequest("lights", ServiceRequestKind.HORN_LIGHT)
    )
    client.async_flash_lights_and_horn = AsyncMock(
        return_value=ServiceRequest("horn", ServiceRequestKind.HORN_LIGHT)
    )
    client.async_start_engine = AsyncMock(
        return_value=ServiceRequest("start", ServiceRequestKind.ENGINE)
    )
    client.async_stop_engine = AsyncMock(
        return_value=ServiceRequest("stop", ServiceRequestKind.ENGINE)
    )
    client.async_refresh_vehicle_status = AsyncMock(
        return_value=ServiceRequest("refresh", ServiceRequestKind.VEHICLE_STATUS)
    )
    client.async_refresh_battery_status = AsyncMock(return_value=True)
    client.async_refresh_climate_status = AsyncMock(return_value=True)
    client.async_wait_for_service_request = AsyncMock(
        return_value=ServiceRequestResult(ServiceRequestStatus.SUCCESS)
    )
    with patch("custom_components.mynissan.create_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    client.coordinator = entry.runtime_data.coordinator
    client.coordinator.async_request_refresh = AsyncMock()
    client.async_lock_doors.assert_not_called()
    client.async_unlock_doors.assert_not_called()
    client.async_flash_lights.assert_not_called()
    client.async_flash_lights_and_horn.assert_not_called()
    client.async_start_engine.assert_not_called()
    client.async_stop_engine.assert_not_called()
    client.async_refresh_vehicle_status.assert_not_called()
    client.async_refresh_battery_status.assert_not_called()
    client.async_refresh_climate_status.assert_not_called()
    return client


async def call_command(hass: HomeAssistant, platform: Platform, key: str, action: str) -> None:
    """Invoke a real Home Assistant service against the mocked vehicle."""
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{VEHICLE.vin}_{key}")
    assert entity_id is not None
    await hass.services.async_call(platform, action, {"entity_id": entity_id}, blocking=True)


async def test_supported_commands(hass: HomeAssistant) -> None:
    """Commands await remote completion without inventing a new lock state."""
    client = await setup_commands(hass)
    assert _entity_state(hass, Platform.LOCK, "door_lock").state == "unlocked"
    await call_command(hass, Platform.LOCK, "door_lock", "lock")
    client.async_lock_doors.assert_awaited_once_with(VEHICLE.vin)
    client.async_wait_for_service_request.assert_awaited_with(
        VEHICLE.vin, ServiceRequest("lock", ServiceRequestKind.DOOR)
    )
    assert _entity_state(hass, Platform.LOCK, "door_lock").state == "unlocked"
    locked_status = replace(VEHICLE_STATUS, doors=replace(DOORS, overall_lock="LOCKED"))
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(locked_status, VEHICLE_LOCATION)}
    )
    assert _entity_state(hass, Platform.LOCK, "door_lock").state == "locked"
    await call_command(hass, Platform.LOCK, "door_lock", "unlock")
    client.async_unlock_doors.assert_awaited_once_with(VEHICLE.vin)
    await call_command(hass, Platform.BUTTON, "flash_lights", "press")
    client.async_flash_lights.assert_awaited_once_with(VEHICLE.vin)
    await call_command(hass, Platform.BUTTON, "flash_lights_and_horn", "press")
    client.async_flash_lights_and_horn.assert_awaited_once_with(VEHICLE.vin)
    assert client.coordinator.async_request_refresh.await_count == 4
    assert client.async_get_vehicle_capabilities.await_count == 5


@pytest.mark.parametrize(("enabled", "subscribed"), [(False, True), (True, False), (True, None)])
async def test_unavailable_services_are_not_exposed(
    hass: HomeAssistant, enabled: bool, subscribed: bool | None
) -> None:
    """Disabled, unsubscribed and unknown subscriptions expose no command controls."""
    services = tuple(replace(s, enabled=enabled, subscribed=subscribed) for s in ALL_SERVICES)
    await setup_commands(hass, services)
    for platform, key in (
        (Platform.LOCK, "door_lock"),
        (Platform.BUTTON, "flash_lights"),
        (Platform.BUTTON, "flash_lights_and_horn"),
    ):
        assert (
            er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{VEHICLE.vin}_{key}") is None
        )


@pytest.mark.parametrize(
    ("services", "lock", "unlock", "combined"),
    [
        ((), False, False, False),
        (("REMOTE_DOOR_LOCK",), True, False, False),
        (("REMOTE_DOOR_UNLOCK",), False, True, False),
        (("REMOTE_DOOR_LOCK", "REMOTE_DOOR_UNLOCK"), False, False, True),
        (("REMOTE_DOOR_LOCK_UNLOCK",), False, False, True),
    ],
)
async def test_directional_lock_services(
    hass: HomeAssistant, services: tuple[str, ...], lock: bool, unlock: bool, combined: bool
) -> None:
    """One-way subscriptions expose only a supported button, not an unsupported action."""
    await setup_commands(hass, tuple(ServiceCapability(s, True, True) for s in services))
    for platform, key, expected in (
        (Platform.BUTTON, "lock_doors", lock),
        (Platform.BUTTON, "unlock_doors", unlock),
        (Platform.LOCK, "door_lock", combined),
    ):
        found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{VEHICLE.vin}_{key}")
        assert (found is not None) == expected
        if expected and platform is Platform.BUTTON:
            await call_command(hass, platform, key, "press")


ENGINE_SERVICES = (ServiceCapability("REMOTE_ENGINE", True, True),)


async def test_remote_engine_commands(hass: HomeAssistant) -> None:
    """Remote start and stop each send one engine request and wait for it."""
    client = await setup_commands(hass, ENGINE_SERVICES)
    assert _entity_state(hass, Platform.SENSOR, "last_remote_engine_start").state == "unknown"
    await call_command(hass, Platform.BUTTON, "remote_engine_start", "press")
    client.async_start_engine.assert_awaited_once_with(
        VEHICLE.vin,
        climate=ClimateSettings(
            22.0,
            TemperatureUnit.CELSIUS,
            ClimateParameters(seats=None, steering_wheel_heater=False, defrost_and_deicer=False),
        ),
    )
    client.async_wait_for_service_request.assert_awaited_with(
        VEHICLE.vin, ServiceRequest("start", ServiceRequestKind.ENGINE)
    )
    await call_command(hass, Platform.BUTTON, "remote_engine_stop", "press")
    client.async_stop_engine.assert_awaited_once_with(VEHICLE.vin)
    client.async_wait_for_service_request.assert_awaited_with(
        VEHICLE.vin, ServiceRequest("stop", ServiceRequestKind.ENGINE)
    )
    assert client.coordinator.async_request_refresh.await_count == 2
    for key in ("last_remote_engine_start", "last_remote_engine_stop"):
        assert _entity_state(hass, Platform.SENSOR, key).state not in ("unknown", "unavailable")


@pytest.mark.parametrize(
    "services",
    [
        ALL_SERVICES,
        (ServiceCapability("REMOTE_ENGINE", False, True),),
        (ServiceCapability("REMOTE_ENGINE", True, None),),
    ],
)
async def test_remote_engine_requires_subscription(
    hass: HomeAssistant, services: tuple[ServiceCapability, ...]
) -> None:
    """Vehicles without an enabled, subscribed REMOTE_ENGINE get no engine buttons."""
    await setup_commands(hass, services)
    for key in ("remote_engine_start", "remote_engine_stop"):
        assert (
            er.async_get(hass).async_get_entity_id(Platform.BUTTON, DOMAIN, f"{VEHICLE.vin}_{key}")
            is None
        )


async def test_remote_engine_rejection_explains_cause(hass: HomeAssistant) -> None:
    """A refused start reports Nissan's reason and does not refresh as if it ran."""
    client = await setup_commands(hass, ENGINE_SERVICES)
    client.async_wait_for_service_request.return_value = ServiceRequestResult(
        ServiceRequestStatus.FAILED, "RES_FAILED"
    )
    with pytest.raises(HomeAssistantError) as error:
        await call_command(hass, Platform.BUTTON, "remote_engine_start", "press")
    assert error.value.translation_key == "engine_command_rejected"
    assert error.value.translation_placeholders == {"status": "FAILED", "details": "RES_FAILED"}
    client.coordinator.async_request_refresh.assert_not_called()
    assert _entity_state(hass, Platform.SENSOR, "last_remote_engine_start").state == "unknown"
    assert (
        _entity_state(hass, Platform.BUTTON, "remote_engine_start").attributes["icon"]
        == "mdi:car-key"
    )


async def test_revoked_engine_subscription_blocks_start(hass: HomeAssistant) -> None:
    """An engine subscription lost after setup must prevent sending the start."""
    client = await setup_commands(hass, ENGINE_SERVICES)
    client.async_get_vehicle_capabilities.return_value = replace(VEHICLE_CAPABILITIES, services=())
    with pytest.raises(ServiceValidationError):
        await call_command(hass, Platform.BUTTON, "remote_engine_start", "press")
    client.async_start_engine.assert_not_called()
    assert (
        _entity_state(hass, Platform.BUTTON, "remote_engine_start").attributes["icon"]
        == "mdi:car-key"
    )


async def test_revoked_subscription_blocks_command(hass: HomeAssistant) -> None:
    """A subscription lost after setup must prevent sending the command."""
    client = await setup_commands(hass)
    client.async_get_vehicle_capabilities.return_value = replace(VEHICLE_CAPABILITIES, services=())
    with pytest.raises(ServiceValidationError):
        await call_command(hass, Platform.LOCK, "door_lock", "unlock")
    client.async_unlock_doors.assert_not_called()
    client.async_wait_for_service_request.assert_not_called()


@pytest.mark.parametrize("error", [NissanError(), TimeoutError()])
async def test_command_errors(hass: HomeAssistant, error: Exception) -> None:
    """Transport errors and timeouts are visible as service failures."""
    client = await setup_commands(hass)
    client.async_wait_for_service_request.side_effect = error
    with pytest.raises(HomeAssistantError):
        await call_command(hass, Platform.BUTTON, "flash_lights", "press")
    client.coordinator.async_request_refresh.assert_not_called()


async def test_failed_remote_result(hass: HomeAssistant) -> None:
    """A completed but rejected command does not imply success."""
    client = await setup_commands(hass)
    client.async_wait_for_service_request.return_value = ServiceRequestResult(
        ServiceRequestStatus.FAILED
    )
    with pytest.raises(HomeAssistantError):
        await call_command(hass, Platform.LOCK, "door_lock", "lock")
    assert _entity_state(hass, Platform.LOCK, "door_lock").state == "unlocked"
    client.coordinator.async_request_refresh.assert_not_called()


async def test_unknown_lock_status(hass: HomeAssistant) -> None:
    """Missing lock data never becomes a locked state."""
    client = await setup_commands(hass)
    for doors in (None, replace(DOORS, overall_lock="UNKNOWN__")):
        status = replace(VEHICLE_STATUS, doors=doors)
        client.coordinator.async_set_updated_data(
            {VEHICLE.vin: NissanVehicleData(status, VEHICLE_LOCATION)}
        )
        assert _entity_state(hass, Platform.LOCK, "door_lock").state == "unknown"
