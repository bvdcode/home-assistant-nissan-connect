"""Tests for climate settings sent with a remote engine start."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pynissan import (
    AccessoryCapability,
    AuthenticationError,
    ClimateDefaults,
    ClimateParameters,
    ClimateSettings,
    HvacTemperatureCapabilities,
    NetworkError,
    NissanError,
    SeatClimateOption,
    SeatClimateSettings,
    SeatHeaterAccessories,
    SeatHeaterCapability,
    ServiceCapability,
    ServiceRequest,
    ServiceRequestKind,
    ServiceRequestResult,
    ServiceRequestStatus,
    TemperatureReading,
    TemperatureUnit,
    VehicleAccessoriesDetails,
)
from pytest_homeassistant_custom_component.common import mock_restore_cache_with_extra_data

from custom_components.mynissan.const import DOMAIN

from .test_init import (
    VEHICLE,
    VEHICLE_CAPABILITIES,
    VEHICLE_LOCATION,
    VEHICLE_STATUS,
    _entity_state,
    _entry,
)

OFF = SeatClimateOption.OFF
HEAT = SeatClimateOption.HEAT
COOL = SeatClimateOption.COOL

# A three-row SUV: ventilated front seats, heated outer second-row seats.
ACCESSORIES = VehicleAccessoriesDetails(
    seat_heater=SeatHeaterCapability(
        True,
        SeatHeaterAccessories(
            assistant_seat="HEATING_AND_COOLING",
            driver_seat="HEATING_AND_COOLING",
            second_centre_seat=None,
            second_left_seat="HEATING",
            second_right_seat="HEATING",
            third_left_seat=None,
            third_right_seat=None,
        ),
    ),
    steering_heat=AccessoryCapability(True),
    sun_roof=None,
    window_status=None,
    way_point=None,
    hvac_temperatures=HvacTemperatureCapabilities(
        unit="FAHRENHEIT", default=75.0, minimum=61.0, maximum=88.0, resolution=1.0
    ),
)
DEFAULTS = ClimateDefaults(
    TemperatureReading(67.0, "FAHRENHEIT"),
    ClimateParameters(
        seats=SeatClimateSettings(
            front_driver=HEAT,
            front_passenger=OFF,
            rear_left=OFF,
            rear_right=OFF,
            rear_center=OFF,
            third_left=OFF,
            third_right=OFF,
        ),
        steering_wheel_heater=True,
        defrost_and_deicer=False,
    ),
)
SEAT_KEYS = (
    "remote_start_front_driver_seat",
    "remote_start_front_passenger_seat",
    "remote_start_rear_left_seat",
    "remote_start_rear_right_seat",
)


async def setup_engine(
    hass: HomeAssistant,
    defaults: ClimateDefaults | Exception | None = DEFAULTS,
    accessories: VehicleAccessoriesDetails | None = ACCESSORIES,
    *,
    setup_succeeds: bool = True,
) -> MagicMock:
    """Load a gasoline vehicle with remote engine start and the given climate support."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = _entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_vehicles = AsyncMock(return_value=(VEHICLE,))
    client.async_get_vehicle_capabilities = AsyncMock(
        return_value=replace(
            VEHICLE_CAPABILITIES,
            services=(ServiceCapability("REMOTE_ENGINE", True, True),),
            accessories_details=accessories,
        )
    )
    client.async_get_vehicle_status = AsyncMock(return_value=VEHICLE_STATUS)
    client.async_get_vehicle_location = AsyncMock(return_value=VEHICLE_LOCATION)
    if isinstance(defaults, Exception):
        client.async_get_climate_defaults = AsyncMock(side_effect=defaults)
    else:
        client.async_get_climate_defaults = AsyncMock(return_value=defaults)
    client.async_start_engine = AsyncMock(
        return_value=ServiceRequest("start", ServiceRequestKind.ENGINE)
    )
    client.async_flash_lights = AsyncMock()
    client.async_wait_for_service_request = AsyncMock(
        return_value=ServiceRequestResult(ServiceRequestStatus.SUCCESS)
    )
    with patch("custom_components.mynissan.create_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id) is setup_succeeds
        await hass.async_block_till_done()
    if setup_succeeds:
        entry.runtime_data.coordinator.async_request_refresh = AsyncMock()
    return client


def _entity_id(hass: HomeAssistant, platform: Platform, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{VEHICLE.vin}_{key}")
    assert entity_id is not None
    return entity_id


def _settings(
    temperature: float = 67.0,
    seats: tuple[SeatClimateOption, SeatClimateOption, SeatClimateOption, SeatClimateOption] = (
        HEAT,
        OFF,
        OFF,
        OFF,
    ),
    steering_wheel_heater: bool = True,
    defrost: bool = False,
) -> ClimateSettings:
    return ClimateSettings(
        temperature,
        TemperatureUnit.FAHRENHEIT,
        ClimateParameters(
            seats=SeatClimateSettings(
                front_driver=seats[0],
                front_passenger=seats[1],
                rear_left=seats[2],
                rear_right=seats[3],
            ),
            steering_wheel_heater=steering_wheel_heater,
            defrost_and_deicer=defrost,
        ),
    )


async def _start(hass: HomeAssistant, **data: object) -> None:
    await hass.services.async_call(
        DOMAIN,
        "remote_engine_start",
        {"entity_id": _entity_id(hass, Platform.BUTTON, "remote_engine_start"), **data},
        blocking=True,
    )


async def test_settings_start_from_app_defaults(hass: HomeAssistant) -> None:
    """Controls exist only for supported seats and begin with the app's saved settings."""
    client = await setup_engine(hass)
    temperature = _entity_state(hass, Platform.NUMBER, "remote_start_temperature")
    assert float(temperature.state) == 67.0
    assert temperature.attributes["min"] == 61.0
    assert temperature.attributes["max"] == 88.0
    driver = _entity_state(hass, Platform.SELECT, "remote_start_front_driver_seat")
    assert driver.state == "heat"
    assert driver.attributes["options"] == ["off", "heat", "cool"]
    rear = _entity_state(hass, Platform.SELECT, "remote_start_rear_left_seat")
    assert rear.attributes["options"] == ["off", "heat"]
    for key in ("remote_start_rear_center_seat", "remote_start_third_left_seat"):
        assert (
            er.async_get(hass).async_get_entity_id(Platform.SELECT, DOMAIN, f"{VEHICLE.vin}_{key}")
            is None
        )
    assert _entity_state(hass, Platform.SWITCH, "remote_start_steering_wheel_heater").state == "on"
    assert _entity_state(hass, Platform.SWITCH, "remote_start_defrost").state == "off"
    client.async_get_climate_defaults.assert_awaited_once_with(
        VEHICLE.vin, temperature_unit=TemperatureUnit.FAHRENHEIT
    )


async def test_start_button_sends_chosen_settings(hass: HomeAssistant) -> None:
    """Changing the controls changes what the start button sends."""
    client = await setup_engine(hass)
    await hass.services.async_call(
        Platform.NUMBER,
        "set_value",
        {"entity_id": _entity_id(hass, Platform.NUMBER, "remote_start_temperature"), "value": 72},
        blocking=True,
    )
    await hass.services.async_call(
        Platform.SELECT,
        "select_option",
        {
            "entity_id": _entity_id(hass, Platform.SELECT, "remote_start_front_passenger_seat"),
            "option": "cool",
        },
        blocking=True,
    )
    await hass.services.async_call(
        Platform.SWITCH,
        "turn_on",
        {"entity_id": _entity_id(hass, Platform.SWITCH, "remote_start_defrost")},
        blocking=True,
    )
    await hass.services.async_call(
        Platform.BUTTON,
        "press",
        {"entity_id": _entity_id(hass, Platform.BUTTON, "remote_engine_start")},
        blocking=True,
    )
    client.async_start_engine.assert_awaited_once_with(
        VEHICLE.vin, climate=_settings(72.0, (HEAT, COOL, OFF, OFF), True, True)
    )


async def test_action_overrides_settings_for_one_start(hass: HomeAssistant) -> None:
    """The action applies its options to one start and leaves the saved controls alone."""
    client = await setup_engine(hass)
    await _start(
        hass,
        temperature=80,
        front_seats="cool",
        rear_seats="heat",
        steering_wheel_heater=False,
        defrost=True,
    )
    client.async_start_engine.assert_awaited_once_with(
        VEHICLE.vin, climate=_settings(80.0, (COOL, COOL, HEAT, HEAT), False, True)
    )
    assert float(_entity_state(hass, Platform.NUMBER, "remote_start_temperature").state) == 67.0
    assert _entity_state(hass, Platform.SELECT, "remote_start_rear_left_seat").state == "off"
    await _start(hass, defrost=True)
    assert client.async_start_engine.await_args.kwargs["climate"] == _settings(defrost=True)
    assert _entity_state(hass, Platform.SENSOR, "last_remote_engine_start").state not in (
        "unknown",
        "unavailable",
    )


@pytest.mark.parametrize(
    ("data", "option"),
    [
        ({"temperature": 95}, "temperature"),
        ({"temperature": 55}, "temperature"),
        ({"rear_seats": "cool"}, "rear_seats"),
    ],
)
async def test_action_rejects_unsupported_settings(
    hass: HomeAssistant, data: dict[str, object], option: str
) -> None:
    """Settings the vehicle cannot use are refused before anything is sent."""
    client = await setup_engine(hass)
    with pytest.raises(ServiceValidationError) as error:
        await _start(hass, **data)
    assert error.value.translation_key == "invalid_remote_start_option"
    assert error.value.translation_placeholders == {"option": option}
    client.async_start_engine.assert_not_called()


async def test_action_requires_start_button(hass: HomeAssistant) -> None:
    """Targeting a different button is refused."""
    client = await setup_engine(hass)
    refresh = _entity_id(hass, Platform.BUTTON, "refresh")
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN, "remote_engine_start", {"entity_id": refresh}, blocking=True
        )
    assert error.value.translation_key == "not_remote_engine_start"
    client.async_start_engine.assert_not_called()


async def test_absent_defaults_use_vehicle_default(hass: HomeAssistant) -> None:
    """Without saved defaults the vehicle's default temperature is used and options are off."""
    client = await setup_engine(hass, defaults=None)
    assert float(_entity_state(hass, Platform.NUMBER, "remote_start_temperature").state) == 75.0
    await _start(hass)
    client.async_start_engine.assert_awaited_once_with(
        VEHICLE.vin, climate=_settings(75.0, (OFF, OFF, OFF, OFF), False, False)
    )


@pytest.mark.parametrize(
    ("error", "state", "reauth"),
    [
        (AuthenticationError(401, "Expired credentials"), ConfigEntryState.SETUP_ERROR, True),
        (NetworkError("Offline"), ConfigEntryState.SETUP_RETRY, False),
        (NissanError("Invalid response"), ConfigEntryState.SETUP_RETRY, False),
    ],
)
async def test_defaults_errors_follow_config_entry_error_handling(
    hass: HomeAssistant, error: NissanError, state: ConfigEntryState, reauth: bool
) -> None:
    """Authentication starts reauth; API failures retry setup instead of replacing settings."""
    client = await setup_engine(hass, defaults=error, setup_succeeds=False)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is state
    assert bool(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) is reauth
    client.async_start_engine.assert_not_called()
    client.async_get_vehicle_status.assert_not_called()


async def test_without_climate_capabilities(hass: HomeAssistant) -> None:
    """Vehicles without HVAC capabilities start with the app's settings and get no controls."""
    client = await setup_engine(hass, defaults=None, accessories=None)
    assert (
        er.async_get(hass).async_get_entity_id(
            Platform.NUMBER, DOMAIN, f"{VEHICLE.vin}_remote_start_temperature"
        )
        is None
    )
    await _start(hass)
    client.async_start_engine.assert_awaited_once_with(VEHICLE.vin, climate=None)
    with pytest.raises(ServiceValidationError):
        await _start(hass, temperature=70)


async def test_settings_survive_restart(hass: HomeAssistant) -> None:
    """Values chosen before a restart are kept instead of the app defaults."""
    last_start = datetime(2026, 11, 1, 12, 30, tzinfo=UTC)
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State("number.family_ariya_remote_start_temperature", "70"),
                {
                    "native_max_value": 88.0,
                    "native_min_value": 61.0,
                    "native_step": 1.0,
                    "native_unit_of_measurement": "°F",
                    "native_value": 70.0,
                },
            ),
            (State("select.family_ariya_remote_start_rear_left_seat", "heat"), {}),
            (State("switch.family_ariya_remote_start_defrost", "on"), {}),
            (
                State("sensor.family_ariya_last_remote_engine_start", last_start.isoformat()),
                {
                    "native_value": {
                        "__type": "<class 'datetime.datetime'>",
                        "isoformat": last_start.isoformat(),
                    },
                    "native_unit_of_measurement": None,
                },
            ),
        ),
    )
    client = await setup_engine(hass)
    assert (
        _entity_state(hass, Platform.SENSOR, "last_remote_engine_start").state
        == last_start.isoformat()
    )
    await _start(hass)
    client.async_start_engine.assert_awaited_once_with(
        VEHICLE.vin, climate=_settings(70.0, (HEAT, OFF, HEAT, OFF), True, True)
    )
