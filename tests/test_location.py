"""Tests for on-demand location updates through the Home Assistant button."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pynissan import (
    NissanError,
    ServiceCapability,
    ServiceRequest,
    ServiceRequestKind,
    ServiceRequestResult,
    ServiceRequestStatus,
    VehicleLocation,
)

from custom_components.mynissan.const import DOMAIN

from .test_commands import call_command, setup_commands
from .test_init import VEHICLE, VEHICLE_LOCATION, _entity_state

LOCATION_SERVICE = ServiceCapability("PARKED_CAR_FINDER", True, True)
CACHED = replace(VEHICLE_LOCATION, last_updated_at=datetime(2026, 1, 1, tzinfo=UTC))
FRESH = replace(CACHED, latitude=0.0, last_updated_at=datetime(2026, 1, 2, tzinfo=UTC))
NEWER = replace(FRESH, last_updated_at=datetime(2026, 1, 3, tzinfo=UTC))


async def setup_location(hass: HomeAssistant, *, subscribed: bool | None = True) -> MagicMock:
    """Load the location tracker and command button with a dated cached fix."""
    return await setup_commands(
        hass, (replace(LOCATION_SERVICE, subscribed=subscribed),), location=CACHED
    )


async def press_location(hass: HomeAssistant) -> None:
    """Press the location button via its standard Home Assistant action."""
    await call_command(hass, Platform.BUTTON, "refresh_location", "press")


@pytest.mark.parametrize("subscribed", [True, False, None])
async def test_refresh_location_publishes_completed_fix(
    hass: HomeAssistant, subscribed: bool | None
) -> None:
    """Dispatch once, await the location result, and preserve it over stale cloud reads."""
    client = await setup_location(hass, subscribed=subscribed)

    async def complete(vin: str, request: ServiceRequest) -> ServiceRequestResult:
        assert vin == VEHICLE.vin
        assert request == ServiceRequest("locate", ServiceRequestKind.LOCATION)
        assert _entity_state(hass, Platform.DEVICE_TRACKER, "location").attributes["latitude"] == (
            CACHED.latitude
        )
        return ServiceRequestResult(ServiceRequestStatus.SUCCESS, location=FRESH)

    client.async_wait_for_service_request.side_effect = complete
    original = client.coordinator.data[VEHICLE.vin]
    await press_location(hass)
    client.async_locate_vehicle.assert_awaited_once_with(VEHICLE.vin)
    client.async_wait_for_service_request.assert_awaited_once()
    client.async_get_vehicle_location.assert_awaited_once()
    client.async_refresh_vehicle_status.assert_not_called()
    client.coordinator.async_request_refresh.assert_not_called()
    assert _entity_state(hass, Platform.DEVICE_TRACKER, "location").attributes["latitude"] == 0.0

    data = client.coordinator.data[VEHICLE.vin]
    assert data == replace(original, location=FRESH)
    await client.coordinator.async_refresh()
    assert client.coordinator.data[VEHICLE.vin].location == FRESH

    client.async_get_vehicle_location.return_value = replace(FRESH, longitude=None)
    await client.coordinator.async_refresh()
    assert client.coordinator.data[VEHICLE.vin].location == FRESH

    client.async_get_vehicle_location.return_value = NEWER
    await client.coordinator.async_refresh()
    assert client.coordinator.data[VEHICLE.vin].location == NEWER


async def test_refresh_location_accepts_first_timestamp(hass: HomeAssistant) -> None:
    """Accept the first fix when Nissan stamps it in the button press second."""
    client = await setup_commands(hass, (LOCATION_SERVICE,))
    client.async_wait_for_service_request.return_value = ServiceRequestResult(
        ServiceRequestStatus.SUCCESS, location=FRESH
    )

    with patch.object(dt_util, "utcnow", return_value=FRESH.last_updated_at):
        await press_location(hass)

    assert client.coordinator.data[VEHICLE.vin].location == FRESH


async def test_incomplete_poll_keeps_last_complete_coordinates(hass: HomeAssistant) -> None:
    """Only a complete position may advance the last known fix on the map."""
    client = await setup_location(hass)
    client.async_get_vehicle_location.return_value = replace(NEWER, longitude=None)
    await client.coordinator.async_refresh()
    tracker = _entity_state(hass, Platform.DEVICE_TRACKER, "location")
    assert tracker.attributes["latitude"] == CACHED.latitude
    assert tracker.attributes["longitude"] == CACHED.longitude

    client.async_wait_for_service_request.return_value = ServiceRequestResult(
        ServiceRequestStatus.SUCCESS, location=FRESH
    )
    await press_location(hass)
    tracker = _entity_state(hass, Platform.DEVICE_TRACKER, "location")
    assert tracker.attributes["latitude"] == FRESH.latitude
    assert tracker.attributes["longitude"] == FRESH.longitude


async def test_refresh_location_preserves_failed_status_poll(hass: HomeAssistant) -> None:
    """A completed locate does not restore unrelated sensors after a poll failure."""
    client = await setup_location(hass)

    async def complete(_vin: str, _request: ServiceRequest) -> ServiceRequestResult:
        client.async_get_vehicle_status.side_effect = NissanError()
        await client.coordinator.async_refresh()
        assert _entity_state(hass, Platform.SENSOR, "battery_level").state == "unavailable"
        assert _entity_state(hass, Platform.DEVICE_TRACKER, "location").state == "unavailable"
        return ServiceRequestResult(ServiceRequestStatus.SUCCESS, location=FRESH)

    client.async_wait_for_service_request.side_effect = complete
    await press_location(hass)

    assert client.coordinator.data[VEHICLE.vin].location == FRESH
    assert _entity_state(hass, Platform.SENSOR, "battery_level").state == "unavailable"
    tracker = _entity_state(hass, Platform.DEVICE_TRACKER, "location")
    assert tracker.attributes["latitude"] == FRESH.latitude
    assert tracker.attributes["longitude"] == FRESH.longitude

    client.async_get_vehicle_status.side_effect = None
    await client.coordinator.async_refresh()
    assert _entity_state(hass, Platform.SENSOR, "battery_level").state == "73"
    client.async_get_vehicle_status.side_effect = NissanError()
    await client.coordinator.async_refresh()
    assert _entity_state(hass, Platform.DEVICE_TRACKER, "location").state == "unavailable"


async def test_refresh_location_keeps_newer_fix_from_poll(hass: HomeAssistant) -> None:
    """A fix newer than the starting position succeeds without rolling back the tracker."""
    client = await setup_location(hass)

    async def complete(_vin: str, _request: ServiceRequest) -> ServiceRequestResult:
        client.async_get_vehicle_location.return_value = NEWER
        await client.coordinator.async_refresh()
        return ServiceRequestResult(ServiceRequestStatus.SUCCESS, location=FRESH)

    client.async_wait_for_service_request.side_effect = complete
    await press_location(hass)

    assert client.coordinator.data[VEHICLE.vin].location == NEWER


async def test_refresh_location_preserves_poll_deadline(hass: HomeAssistant) -> None:
    """Completing a locate leaves the existing account poll scheduled."""
    client = await setup_location(hass)
    client.async_wait_for_service_request.return_value = ServiceRequestResult(
        ServiceRequestStatus.SUCCESS, location=FRESH
    )

    pending_refresh = client.coordinator._unsub_refresh
    assert pending_refresh is not None
    await press_location(hass)

    assert client.coordinator._unsub_refresh is pending_refresh


@pytest.mark.parametrize(
    "location",
    [
        None,
        CACHED,
        replace(CACHED, last_updated_at=datetime(2025, 12, 31, tzinfo=UTC)),
        replace(FRESH, latitude=None),
        replace(FRESH, longitude=None),
        replace(FRESH, last_updated_at=None),
        replace(FRESH, last_updated_at=datetime(2026, 1, 2)),
    ],
)
async def test_refresh_location_requires_fresh_fix(
    hass: HomeAssistant, location: VehicleLocation | None
) -> None:
    """A success status alone leaves the old tracker state and fails the action."""
    client = await setup_location(hass)
    client.async_wait_for_service_request.return_value = ServiceRequestResult(
        ServiceRequestStatus.SUCCESS, location=location
    )
    with pytest.raises(HomeAssistantError) as error:
        await press_location(hass)
    assert error.value.translation_key == "location_not_updated"
    assert client.coordinator.data[VEHICLE.vin].location == CACHED


@pytest.mark.parametrize("failure", [NissanError(), TimeoutError(), ServiceRequestStatus.FAILED])
async def test_location_command_failure(
    hass: HomeAssistant, failure: Exception | ServiceRequestStatus
) -> None:
    """Timeouts, transport failures, and remote rejections fail the action."""
    client = await setup_location(hass)
    if isinstance(failure, Exception):
        client.async_wait_for_service_request.side_effect = failure
    else:
        client.async_wait_for_service_request.return_value = ServiceRequestResult(
            failure, location=FRESH
        )
    with pytest.raises(HomeAssistantError):
        await press_location(hass)
    assert client.coordinator.data[VEHICLE.vin].location == CACHED


@pytest.mark.parametrize(
    "services",
    [
        (),
        (replace(LOCATION_SERVICE, enabled=False),),
    ],
)
async def test_location_button_requires_enabled_service(
    hass: HomeAssistant, services: tuple[ServiceCapability, ...]
) -> None:
    """Only vehicles with Parked Car Finder enabled expose the locate button."""
    await setup_commands(hass, services)
    assert (
        er.async_get(hass).async_get_entity_id(
            Platform.BUTTON, DOMAIN, f"{VEHICLE.vin}_refresh_location"
        )
        is None
    )


async def test_removed_location_capability_blocks_dispatch(hass: HomeAssistant) -> None:
    """Recheck the service before sending a request that can wake the vehicle."""
    client = await setup_location(hass)
    caps = client.async_get_vehicle_capabilities.return_value
    client.async_get_vehicle_capabilities.return_value = replace(caps, services=())
    with pytest.raises(ServiceValidationError):
        await press_location(hass)
    client.async_locate_vehicle.assert_not_called()


async def test_unavailable_vehicle_blocks_location_dispatch(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """An unavailable command entity rejects a press without waking the vehicle."""
    client = await setup_location(hass)
    client.coordinator.async_set_update_error(NissanError())
    assert _entity_state(hass, Platform.BUTTON, "refresh_location").state == "unavailable"
    await press_location(hass)
    assert "are missing or not currently available" in caplog.text
    client.async_locate_vehicle.assert_not_called()
