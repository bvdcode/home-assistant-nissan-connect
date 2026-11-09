"""Tests for hourglass icons while remote button commands run."""

import asyncio
from unittest.mock import MagicMock

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pynissan import (
    NissanError,
    ServiceCapability,
    ServiceRequest,
    ServiceRequestResult,
    ServiceRequestStatus,
)

from custom_components.mynissan.const import DOMAIN, SERVICE_REMOTE_ENGINE_START

from .test_commands import call_command, setup_commands
from .test_init import _entity_state

BUTTON_CASES = (
    ("refresh", ()),
    ("flash_lights", ("REMOTE_HORN_LIGHTS",)),
    ("flash_lights_and_horn", ("REMOTE_HORN_LIGHTS",)),
    ("lock_doors", ("REMOTE_DOOR_LOCK",)),
    ("unlock_doors", ("REMOTE_DOOR_UNLOCK",)),
    ("remote_engine_start", ("REMOTE_ENGINE",)),
    ("remote_engine_stop", ("REMOTE_ENGINE",)),
)


@pytest.mark.parametrize(("key", "services"), BUTTON_CASES)
async def test_button_hourglass_until_command_finishes(
    hass: HomeAssistant, key: str, services: tuple[str, ...]
) -> None:
    """Every button shows progress through remote completion and the status read."""
    client = await setup_commands(
        hass, tuple(ServiceCapability(service, True, True) for service in services)
    )
    normal_icon = _entity_state(hass, Platform.BUTTON, key).attributes["icon"]

    def assert_pending() -> None:
        state = _entity_state(hass, Platform.BUTTON, key)
        assert state.attributes["icon"] == "mdi:timer-sand"
        assert state.state not in ("unknown", "unavailable")
        client.coordinator.async_update_listeners()
        assert _entity_state(hass, Platform.BUTTON, key).attributes["icon"] == "mdi:timer-sand"
        if key != "refresh":
            assert (
                _entity_state(hass, Platform.BUTTON, "refresh").attributes["icon"] == "mdi:refresh"
            )

    async def wait(vin: str, request: ServiceRequest) -> ServiceRequestResult:
        assert_pending()
        return ServiceRequestResult(ServiceRequestStatus.SUCCESS)

    async def refresh_section(vin: str) -> bool:
        assert_pending()
        return True

    async def read_status() -> None:
        assert_pending()

    client.async_wait_for_service_request.side_effect = wait
    client.async_refresh_battery_status.side_effect = refresh_section
    client.async_refresh_climate_status.side_effect = refresh_section
    client.coordinator.async_request_refresh.side_effect = read_status

    await call_command(hass, Platform.BUTTON, key, "press")

    assert _entity_state(hass, Platform.BUTTON, key).attributes["icon"] == normal_icon


@pytest.mark.parametrize("error", [NissanError(), TimeoutError(), asyncio.CancelledError()])
async def test_button_errors_restore_icon(hass: HomeAssistant, error: BaseException) -> None:
    """Transport errors, timeouts and cancellation all restore the normal icon."""
    client = await setup_commands(hass)
    client.async_wait_for_service_request.side_effect = error
    expected_error = (
        asyncio.CancelledError if isinstance(error, asyncio.CancelledError) else HomeAssistantError
    )

    with pytest.raises(expected_error):
        await call_command(hass, Platform.BUTTON, "flash_lights", "press")

    assert (
        _entity_state(hass, Platform.BUTTON, "flash_lights").attributes["icon"]
        == "mdi:car-light-high"
    )


@pytest.mark.parametrize("step", ["battery", "climate"])
async def test_refresh_failure_restores_icon(hass: HomeAssistant, step: str) -> None:
    """A failed battery or climate update cannot leave the Refresh hourglass active."""
    client = await setup_commands(hass)
    operations = {
        "battery": client.async_refresh_battery_status,
        "climate": client.async_refresh_climate_status,
    }
    operations[step].return_value = False

    with pytest.raises(HomeAssistantError):
        await call_command(hass, Platform.BUTTON, "refresh", "press")

    assert _entity_state(hass, Platform.BUTTON, "refresh").attributes["icon"] == "mdi:refresh"


async def test_remote_start_service_shows_hourglass(hass: HomeAssistant) -> None:
    """The dedicated engine start service uses the same progress icon as a button press."""
    client = await setup_commands(hass, (ServiceCapability("REMOTE_ENGINE", True, True),))
    entity_id = _entity_state(hass, Platform.BUTTON, "remote_engine_start").entity_id

    async def wait(vin: str, request: ServiceRequest) -> ServiceRequestResult:
        state = _entity_state(hass, Platform.BUTTON, "remote_engine_start")
        assert state.attributes["icon"] == "mdi:timer-sand"
        return ServiceRequestResult(ServiceRequestStatus.SUCCESS)

    client.async_wait_for_service_request.side_effect = wait

    await hass.services.async_call(
        DOMAIN, SERVICE_REMOTE_ENGINE_START, {"entity_id": entity_id}, blocking=True
    )

    assert (
        _entity_state(hass, Platform.BUTTON, "remote_engine_start").attributes["icon"]
        == "mdi:car-key"
    )


@pytest.mark.parametrize("first_fails", [False, True])
async def test_overlapping_presses_keep_hourglass(hass: HomeAssistant, first_fails: bool) -> None:
    """A finishing or failed press cannot clear another pending press's hourglass."""
    client: MagicMock = await setup_commands(hass)
    started = (asyncio.Event(), asyncio.Event())
    finish = (asyncio.Event(), asyncio.Event())
    indices = iter(range(2))

    async def wait(vin: str, request: ServiceRequest) -> ServiceRequestResult:
        index = next(indices)
        started[index].set()
        await finish[index].wait()
        if index == 0 and first_fails:
            raise NissanError()
        return ServiceRequestResult(ServiceRequestStatus.SUCCESS)

    client.async_wait_for_service_request.side_effect = wait
    tasks: list[asyncio.Task[None]] = []
    try:
        for event in started:
            tasks.append(
                asyncio.create_task(call_command(hass, Platform.BUTTON, "flash_lights", "press"))
            )
            async with asyncio.timeout(5):
                await event.wait()
        finish[0].set()
        if first_fails:
            with pytest.raises(HomeAssistantError):
                await tasks[0]
        else:
            await tasks[0]
        assert (
            _entity_state(hass, Platform.BUTTON, "flash_lights").attributes["icon"]
            == "mdi:timer-sand"
        )
    finally:
        for event in finish:
            event.set()
        await asyncio.gather(*tasks, return_exceptions=True)

    assert (
        _entity_state(hass, Platform.BUTTON, "flash_lights").attributes["icon"]
        == "mdi:car-light-high"
    )
