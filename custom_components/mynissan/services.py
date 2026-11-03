"""Remote engine start action with per-start climate settings."""

from collections.abc import Mapping
from typing import NoReturn

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import VolDictType
from pynissan import SeatClimateOption

from .button import NissanEngineStartButton
from .const import DOMAIN, SERVICE_REMOTE_ENGINE_START
from .engine_climate import EngineClimate

ATTR_TEMPERATURE = "temperature"
ATTR_FRONT_SEATS = "front_seats"
ATTR_REAR_SEATS = "rear_seats"
ATTR_STEERING_WHEEL_HEATER = "steering_wheel_heater"
ATTR_DEFROST = "defrost"

SEAT_GROUPS: dict[str, tuple[str, ...]] = {
    ATTR_FRONT_SEATS: ("front_driver", "front_passenger"),
    ATTR_REAR_SEATS: ("rear_left", "rear_right", "rear_center", "third_left", "third_right"),
}
SEAT_MODES = [option.value.lower() for option in SeatClimateOption if option.value != "UNKNOWN__"]

START_SCHEMA: VolDictType = {
    vol.Optional(ATTR_TEMPERATURE): vol.Coerce(float),
    vol.Optional(ATTR_FRONT_SEATS): vol.In(SEAT_MODES),
    vol.Optional(ATTR_REAR_SEATS): vol.In(SEAT_MODES),
    vol.Optional(ATTR_STEERING_WHEEL_HEATER): cv.boolean,
    vol.Optional(ATTR_DEFROST): cv.boolean,
}


START_OPTIONS = (
    ATTR_TEMPERATURE,
    ATTR_FRONT_SEATS,
    ATTR_REAR_SEATS,
    ATTR_STEERING_WHEEL_HEATER,
    ATTR_DEFROST,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the remote engine start action."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_REMOTE_ENGINE_START,
        entity_domain=Platform.BUTTON,
        schema=START_SCHEMA,
        func=_async_remote_engine_start,
    )


async def _async_remote_engine_start(entity: Entity, call: ServiceCall) -> None:
    """Start the engine with the given settings, keeping the saved ones for anything omitted."""
    if not isinstance(entity, NissanEngineStartButton):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_remote_engine_start",
            translation_placeholders={"entity_id": entity.entity_id},
        )
    data = call.data
    climate = entity.climate
    if climate is None:
        # Without reported HVAC capabilities the vehicle uses its own saved settings.
        if requested := sorted(data.keys() & {*START_OPTIONS}):
            _invalid_option(requested[0])
        await entity.async_start_engine()
        return

    temperature: float | None = data.get(ATTR_TEMPERATURE)
    if temperature is not None and not climate.minimum <= temperature <= climate.maximum:
        _invalid_option(ATTR_TEMPERATURE)
    if ATTR_STEERING_WHEEL_HEATER in data and climate.steering_wheel_heater is None:
        _invalid_option(ATTR_STEERING_WHEEL_HEATER)
    await entity.async_start_engine(
        temperature=temperature,
        seats=_seat_overrides(climate, data),
        steering_wheel_heater=data.get(ATTR_STEERING_WHEEL_HEATER),
        defrost=data.get(ATTR_DEFROST),
    )


def _seat_overrides(
    climate: EngineClimate, data: Mapping[str, object]
) -> dict[str, SeatClimateOption]:
    """Apply a front or rear seat mode to every supported seat in that row group."""
    seats: dict[str, SeatClimateOption] = {}
    for group, positions in SEAT_GROUPS.items():
        if group not in data:
            continue
        mode = SeatClimateOption(str(data[group]).upper())
        supported = [position for position in positions if position in climate.seat_options]
        if mode is not SeatClimateOption.OFF and not supported:
            _invalid_option(group)
        for position in supported:
            if mode not in climate.seat_options[position]:
                _invalid_option(group)
            seats[position] = mode
    return seats


def _invalid_option(option: str) -> NoReturn:
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_remote_start_option",
        translation_placeholders={"option": option},
    )
