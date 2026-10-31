"""Tests for explicit vehicle refresh through the button service."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pynissan import (
    NissanError,
    ServiceRequest,
    ServiceRequestKind,
    ServiceRequestResult,
    ServiceRequestStatus,
)

from custom_components.mynissan.coordinator import NissanDataUpdateCoordinator, NissanVehicleData

from .test_commands import call_command, setup_commands
from .test_init import VEHICLE, VEHICLE_LOCATION, VEHICLE_STATUS, _entity_state


async def test_regular_update_does_not_request_vehicle_refresh(hass: HomeAssistant) -> None:
    """Startup and coordinator updates only read cached status without waking the vehicle."""
    client = await setup_commands(hass)

    await client.coordinator.async_refresh()

    client.async_refresh_vehicle_status.assert_not_called()
    client.async_wait_for_service_request.assert_not_called()
    client.async_refresh_battery_status.assert_not_called()
    client.async_refresh_climate_status.assert_not_called()
    assert client.async_get_vehicle_status.await_count == 2


async def test_refresh_updates_vehicle_readings(hass: HomeAssistant) -> None:
    """Refresh waits for the vehicle, updates battery/climate, then reloads readings."""
    client = await setup_commands(hass, ())
    assert _entity_state(hass, Platform.BUTTON, "refresh").state == "unknown"
    assert VEHICLE_STATUS.battery is not None
    updated = replace(
        client.async_get_vehicle_status.return_value,
        battery=replace(VEHICLE_STATUS.battery, level=88),
    )
    client.async_get_vehicle_status.return_value = updated
    client.coordinator.async_request_refresh = AsyncMock(
        wraps=NissanDataUpdateCoordinator.async_request_refresh.__get__(client.coordinator)
    )
    order = MagicMock()
    order.attach_mock(client.async_refresh_vehicle_status, "vehicle")
    order.attach_mock(client.async_wait_for_service_request, "wait")
    order.attach_mock(client.async_refresh_battery_status, "battery")
    order.attach_mock(client.async_refresh_climate_status, "climate")
    order.attach_mock(client.coordinator.async_request_refresh, "read")

    await call_command(hass, Platform.BUTTON, "refresh", "press")

    assert order.mock_calls == [
        call.vehicle(VEHICLE.vin),
        call.wait(VEHICLE.vin, ServiceRequest("refresh", ServiceRequestKind.VEHICLE_STATUS)),
        call.battery(VEHICLE.vin),
        call.climate(VEHICLE.vin),
        call.read(),
    ]
    assert _entity_state(hass, Platform.SENSOR, "battery_level").state == "88"
    assert client.async_get_vehicle_status.await_count == 2
    assert client.async_get_vehicle_location.await_count == 2


@pytest.mark.parametrize(("battery", "climate"), [(False, False), (False, True), (True, False)])
async def test_refresh_only_reported_sections(
    hass: HomeAssistant, battery: bool, climate: bool
) -> None:
    """Vehicles without battery or climate data still support general status refresh."""
    client = await setup_commands(hass, ())
    status = replace(
        VEHICLE_STATUS,
        battery=VEHICLE_STATUS.battery if battery else None,
        climate=VEHICLE_STATUS.climate if climate else None,
    )
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(status, VEHICLE_LOCATION)}
    )

    await call_command(hass, Platform.BUTTON, "refresh", "press")

    client.async_refresh_vehicle_status.assert_awaited_once_with(VEHICLE.vin)
    assert client.async_refresh_battery_status.await_count == int(battery)
    assert client.async_refresh_climate_status.await_count == int(climate)
    client.coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.parametrize(
    "status", [ServiceRequestStatus.FAILED, ServiceRequestStatus.UNKNOWN, None]
)
async def test_refresh_rejected_request(
    hass: HomeAssistant, status: ServiceRequestStatus | None
) -> None:
    """A rejected vehicle refresh prevents subsequent battery and climate requests."""
    client = await setup_commands(hass)
    client.async_wait_for_service_request.return_value = ServiceRequestResult(status)

    with pytest.raises(HomeAssistantError) as raised:
        await call_command(hass, Platform.BUTTON, "refresh", "press")

    assert raised.value.translation_key == "command_rejected"
    client.async_refresh_battery_status.assert_not_called()
    client.async_refresh_climate_status.assert_not_called()
    client.coordinator.async_request_refresh.assert_not_called()


@pytest.mark.parametrize("error", [NissanError(), TimeoutError()])
@pytest.mark.parametrize("step", ["request", "wait", "battery", "climate"])
async def test_refresh_sdk_errors(hass: HomeAssistant, step: str, error: Exception) -> None:
    """Errors at any refresh stage become translated Home Assistant service errors."""
    client = await setup_commands(hass)
    operations = {
        "request": client.async_refresh_vehicle_status,
        "wait": client.async_wait_for_service_request,
        "battery": client.async_refresh_battery_status,
        "climate": client.async_refresh_climate_status,
    }
    operations[step].side_effect = error

    with pytest.raises(HomeAssistantError) as raised:
        await call_command(hass, Platform.BUTTON, "refresh", "press")

    assert raised.value.translation_key == "command_failed"
    assert raised.value.__cause__ is error
    client.coordinator.async_request_refresh.assert_not_called()
    if step in ("request", "wait"):
        client.async_refresh_battery_status.assert_not_called()
    if step != "climate":
        client.async_refresh_climate_status.assert_not_called()


@pytest.mark.parametrize("step", ["battery", "climate"])
async def test_refresh_unsuccessful_response(hass: HomeAssistant, step: str) -> None:
    """A false success result cannot be reported as a completed refresh."""
    client = await setup_commands(hass)
    operations = {
        "battery": client.async_refresh_battery_status,
        "climate": client.async_refresh_climate_status,
    }
    operations[step].return_value = False

    with pytest.raises(HomeAssistantError) as raised:
        await call_command(hass, Platform.BUTTON, "refresh", "press")

    assert raised.value.translation_key == "command_failed"
    client.coordinator.async_request_refresh.assert_not_called()
    if step == "battery":
        client.async_refresh_climate_status.assert_not_called()
