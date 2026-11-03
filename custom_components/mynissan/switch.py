"""Steering wheel heat and defrost requested with each remote engine start."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import Vehicle

from .coordinator import NissanDataUpdateCoordinator
from .engine_climate import EngineClimate
from .engine_settings import NissanEngineSetting
from .models import NissanConfigEntry


@dataclass(frozen=True, kw_only=True)
class NissanEngineSwitchDescription(SwitchEntityDescription):
    """Describe an on/off option of the remote start climate request."""

    supported_fn: Callable[[EngineClimate], bool]
    value_fn: Callable[[EngineClimate], bool]
    set_fn: Callable[[EngineClimate, bool], None]


def _set_steering_wheel_heater(climate: EngineClimate, value: bool) -> None:
    climate.steering_wheel_heater = value


def _set_defrost(climate: EngineClimate, value: bool) -> None:
    climate.defrost = value


SWITCH_DESCRIPTIONS = (
    NissanEngineSwitchDescription(
        key="remote_start_steering_wheel_heater",
        translation_key="remote_start_steering_wheel_heater",
        icon="mdi:steering",
        supported_fn=lambda climate: climate.steering_wheel_heater is not None,
        value_fn=lambda climate: climate.steering_wheel_heater is True,
        set_fn=_set_steering_wheel_heater,
    ),
    NissanEngineSwitchDescription(
        key="remote_start_defrost",
        translation_key="remote_start_defrost",
        icon="mdi:car-defrost-front",
        supported_fn=lambda climate: True,
        value_fn=lambda climate: climate.defrost,
        set_fn=_set_defrost,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose the on/off remote start options each vehicle supports."""
    del hass
    runtime = entry.runtime_data
    async_add_entities(
        NissanEngineSwitch(runtime.coordinator, vehicle, climate, description)
        for vehicle in runtime.vehicles
        if (climate := runtime.engine_climate.get(vehicle.vin)) is not None
        for description in SWITCH_DESCRIPTIONS
        if description.supported_fn(climate)
    )


class NissanEngineSwitch(NissanEngineSetting, SwitchEntity):
    """Turn one climate option on or off for the next remote engine start."""

    entity_description: NissanEngineSwitchDescription

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
        climate: EngineClimate,
        description: NissanEngineSwitchDescription,
    ) -> None:
        """Initialize the option switch."""
        self.entity_description = description
        super().__init__(coordinator, vehicle, climate)

    async def async_added_to_hass(self) -> None:
        """Keep the choice made before Home Assistant restarted."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in (STATE_ON, STATE_OFF):
            self.entity_description.set_fn(self._climate, last.state == STATE_ON)

    @property
    def is_on(self) -> bool:
        """Return whether the option is sent turned on."""
        return self.entity_description.value_fn(self._climate)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the option turned on with the next start."""
        self.entity_description.set_fn(self._climate, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the option turned off with the next start."""
        self.entity_description.set_fn(self._climate, False)
        self.async_write_ha_state()
