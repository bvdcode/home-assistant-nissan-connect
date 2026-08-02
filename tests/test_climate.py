"""Tests for MyNISSAN climate control."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_EMAIL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pynissan import (
    ClimateSettings,
    ClimateStatus,
    HvacTemperatureCapabilities,
    ServiceCapability,
    ServiceRequest,
    ServiceRequestKind,
    ServiceRequestResult,
    ServiceRequestStatus,
    TemperatureReading,
    TemperatureUnit,
    Vehicle,
    VehicleAccessoriesDetails,
    VehicleCapabilities,
    VehicleLocation,
    VehicleStatus,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mynissan.const import (
    CONF_AUTH_PROFILE,
    CONF_COUNTRY,
    CONF_OAUTH_DEVICE_ID,
    CONF_TOKENS,
    DOMAIN,
    MOBILE_AUTH_PROFILE,
)

VEHICLE = Vehicle("JN1TESTVIN0000001", "2025", "ARIYA", None, "Ariya", None, None, None)
CAPABILITIES = VehicleCapabilities(
    vin=VEHICLE.vin,
    telematics_program="NISSAN_CONNECT",
    enrollment_status="ENROLLED",
    services=(ServiceCapability("CLIMATE_CONTROL", True, True),),
    accessories_details=VehicleAccessoriesDetails(
        seat_heater=None,
        steering_heat=None,
        sun_roof=None,
        window_status=None,
        way_point=None,
        hvac_temperatures=HvacTemperatureCapabilities(
            unit=TemperatureUnit.CELSIUS.value,
            default=22.0,
            minimum=16.0,
            maximum=30.0,
            resolution=0.5,
        ),
    ),
)


async def test_climate_entity_controls_vehicle(hass: HomeAssistant) -> None:
    """Climate services start, adjust, and stop the vehicle climate system."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="US:driver@example.com",
        title="driver@example.com",
        data={
            CONF_AUTH_PROFILE: MOBILE_AUTH_PROFILE,
            CONF_COUNTRY: "US",
            CONF_EMAIL: "driver@example.com",
            CONF_OAUTH_DEVICE_ID: "oauth-device-id",
            CONF_TOKENS: {
                "access_token": "access",
                "refresh_token": "refresh",
                "id_token": "id",
            },
        },
    )
    entry.add_to_hass(hass)

    client = MagicMock()
    client.async_get_vehicles = AsyncMock(return_value=(VEHICLE,))
    client.async_get_vehicle_capabilities = AsyncMock(return_value=CAPABILITIES)
    client.async_get_vehicle_status = AsyncMock(
        side_effect=(
            _status("OFF", 55.0),
            _status("ON", 24.0),
            _status("ON", 23.0),
            _status("OFF", 55.0),
        )
    )
    client.async_get_vehicle_location = AsyncMock(
        return_value=VehicleLocation(VEHICLE.vin, 32.7157, -117.1611, None)
    )
    client.async_start_climate = AsyncMock(
        return_value=ServiceRequest("start", ServiceRequestKind.CLIMATE)
    )
    client.async_adjust_climate = AsyncMock(
        return_value=ServiceRequest("adjust", ServiceRequestKind.CLIMATE)
    )
    client.async_stop_climate = AsyncMock(
        return_value=ServiceRequest("stop", ServiceRequestKind.CLIMATE)
    )
    client.async_wait_for_service_request = AsyncMock(
        return_value=ServiceRequestResult(ServiceRequestStatus.SUCCESS)
    )

    with patch("custom_components.mynissan.create_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "climate",
        DOMAIN,
        f"{VEHICLE.vin}_climate_control",
    )
    assert entity_id is not None

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 24.0},
        blocking=True,
    )
    client.async_start_climate.assert_not_called()

    await hass.services.async_call(
        "climate",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    client.async_start_climate.assert_awaited_once_with(
        VEHICLE.vin,
        ClimateSettings(24.0, TemperatureUnit.CELSIUS),
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )
    client.async_adjust_climate.assert_awaited_once_with(
        VEHICLE.vin,
        ClimateSettings(23.0, TemperatureUnit.CELSIUS),
    )

    await hass.services.async_call(
        "climate",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    client.async_stop_climate.assert_awaited_once_with(VEHICLE.vin)


def _status(state: str, temperature: float) -> VehicleStatus:
    return VehicleStatus(
        vin=VEHICLE.vin,
        vehicle_type="ElectricAVK2Vehicle",
        battery=None,
        climate=ClimateStatus(state, TemperatureReading(temperature, "CELSIUS")),
        doors=None,
        fuel_range=None,
        mileage=None,
        tire_pressure=None,
        maintenance_indicators=(),
    )
