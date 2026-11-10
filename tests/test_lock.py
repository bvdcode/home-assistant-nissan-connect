"""Tests for visible progress of remote door lock commands."""

import asyncio
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pynissan import NissanError, ServiceRequest, ServiceRequestResult, ServiceRequestStatus

from custom_components.mynissan.coordinator import NissanVehicleData
from custom_components.mynissan.lock import NissanDoorLock

from .test_commands import call_command, setup_commands
from .test_doors import DOORS
from .test_init import VEHICLE, VEHICLE_LOCATION, VEHICLE_STATUS, _entity_state

LOCK_ACTIONS = (
    ("lock", "UNLOCKED", "LOCKED", "locking"),
    ("unlock", "LOCKED", "UNLOCKED", "unlocking"),
)


def set_reported_lock(client: MagicMock, state: str) -> None:
    """Publish the vehicle's reported door lock state."""
    status = replace(VEHICLE_STATUS, doors=replace(DOORS, overall_lock=state))
    client.coordinator.async_set_updated_data(
        {VEHICLE.vin: NissanVehicleData(status, VEHICLE_LOCATION)}
    )


@pytest.mark.parametrize(("action", "initial", "target", "progress"), LOCK_ACTIONS)
@pytest.mark.parametrize("step", ["capabilities", "request", "wait", "refresh"])
async def test_lock_progress_until_status_read(
    hass: HomeAssistant, action: str, initial: str, target: str, progress: str, step: str
) -> None:
    """Show progress through every command stage, including the final status read."""
    client = await setup_commands(hass)
    set_reported_lock(client, initial)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def refresh() -> None:
        set_reported_lock(client, target)

    client.coordinator.async_request_refresh.side_effect = refresh
    operations = {
        "capabilities": client.async_get_vehicle_capabilities,
        "request": getattr(client, f"async_{action}_doors"),
        "wait": client.async_wait_for_service_request,
        "refresh": client.coordinator.async_request_refresh,
    }
    operation = operations[step]
    result = operation.return_value

    async def pause(*args: object, **kwargs: object) -> object:
        started.set()
        await finish.wait()
        if step == "refresh":
            await refresh()
        return result

    operation.side_effect = pause
    command = asyncio.create_task(call_command(hass, Platform.LOCK, "door_lock", action))
    try:
        async with asyncio.timeout(5):
            await started.wait()
        assert _entity_state(hass, Platform.LOCK, "door_lock").state == progress
        assert client.coordinator.data[VEHICLE.vin].status.doors.overall_lock == initial
        set_reported_lock(client, initial)
        assert _entity_state(hass, Platform.LOCK, "door_lock").state == progress
    finally:
        finish.set()
        await command

    assert _entity_state(hass, Platform.LOCK, "door_lock").state == target.lower()


@pytest.mark.parametrize(("action", "initial", "target", "progress"), LOCK_ACTIONS)
@pytest.mark.parametrize(
    ("step", "error"),
    [
        ("capabilities", NissanError()),
        ("request", NissanError()),
        ("wait", TimeoutError()),
        ("refresh", HomeAssistantError("Unable to read vehicle status")),
    ],
)
async def test_failed_lock_clears_progress(
    hass: HomeAssistant,
    action: str,
    initial: str,
    target: str,
    progress: str,
    step: str,
    error: Exception,
) -> None:
    """A failed command restores reported status instead of leaving progress active."""
    client = await setup_commands(hass)
    set_reported_lock(client, initial)
    operations = {
        "capabilities": client.async_get_vehicle_capabilities,
        "request": getattr(client, f"async_{action}_doors"),
        "wait": client.async_wait_for_service_request,
        "refresh": client.coordinator.async_request_refresh,
    }
    operations[step].side_effect = error

    with pytest.raises(HomeAssistantError):
        await call_command(hass, Platform.LOCK, "door_lock", action)

    assert _entity_state(hass, Platform.LOCK, "door_lock").state == initial.lower()


@pytest.mark.parametrize(("action", "initial", "target", "progress"), LOCK_ACTIONS)
async def test_cancelled_lock_clears_progress(
    hass: HomeAssistant, action: str, initial: str, target: str, progress: str
) -> None:
    """Cancellation cannot leave a lock in a permanent transition."""
    client = await setup_commands(hass)
    set_reported_lock(client, initial)
    client.async_wait_for_service_request.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await call_command(hass, Platform.LOCK, "door_lock", action)

    assert _entity_state(hass, Platform.LOCK, "door_lock").state == initial.lower()
    client.coordinator.async_request_refresh.assert_not_called()


async def test_lock_commands_do_not_overlap(hass: HomeAssistant) -> None:
    """A queued opposite command starts only after the first command has finished."""
    client = await setup_commands(hass)
    entity_id = _entity_state(hass, Platform.LOCK, "door_lock").entity_id
    entity = hass.data[Platform.LOCK].get_entity(entity_id)
    assert isinstance(entity, NissanDoorLock)
    started = {"lock": asyncio.Event(), "unlock": asyncio.Event()}
    finish = {"lock": asyncio.Event(), "unlock": asyncio.Event()}
    queued = asyncio.Event()

    async def wait(vin: str, request: ServiceRequest) -> ServiceRequestResult:
        started[request.id].set()
        await finish[request.id].wait()
        return ServiceRequestResult(ServiceRequestStatus.SUCCESS)

    async def unlock() -> None:
        queued.set()
        await entity.async_unlock()

    client.async_wait_for_service_request.side_effect = wait
    first = asyncio.create_task(entity.async_lock())
    second: asyncio.Task[None] | None = None
    try:
        async with asyncio.timeout(5):
            await started["lock"].wait()
        second = asyncio.create_task(unlock())
        async with asyncio.timeout(5):
            await queued.wait()
        client.async_unlock_doors.assert_not_called()
        assert _entity_state(hass, Platform.LOCK, "door_lock").state == "locking"
        finish["lock"].set()
        await first
        async with asyncio.timeout(5):
            await started["unlock"].wait()
        assert _entity_state(hass, Platform.LOCK, "door_lock").state == "unlocking"
    finally:
        finish["lock"].set()
        finish["unlock"].set()
        await first
        if second is not None:
            await second

    assert _entity_state(hass, Platform.LOCK, "door_lock").state == "unlocked"
