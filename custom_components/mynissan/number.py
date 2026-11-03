"""Cabin temperature requested with each remote engine start."""

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    RestoreNumber,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import Vehicle

from .climate import _temperature_unit
from .coordinator import NissanDataUpdateCoordinator
from .engine_climate import EngineClimate
from .engine_settings import NissanEngineSetting
from .models import NissanConfigEntry

TEMPERATURE_DESCRIPTION = NumberEntityDescription(
    key="remote_start_temperature",
    translation_key="remote_start_temperature",
    icon="mdi:thermometer-auto",
    device_class=NumberDeviceClass.TEMPERATURE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose the remote start temperature for vehicles with remote engine start."""
    del hass
    runtime = entry.runtime_data
    async_add_entities(
        NissanEngineTemperature(runtime.coordinator, vehicle, runtime.engine_climate[vehicle.vin])
        for vehicle in runtime.vehicles
        if vehicle.vin in runtime.engine_climate
    )


class NissanEngineTemperature(NissanEngineSetting, RestoreNumber):
    """Target cabin temperature for the next remote engine start."""

    entity_description = TEMPERATURE_DESCRIPTION

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
        climate: EngineClimate,
    ) -> None:
        """Initialize the temperature setting with the vehicle's supported range."""
        super().__init__(coordinator, vehicle, climate)
        self._attr_native_min_value = climate.minimum
        self._attr_native_max_value = climate.maximum
        self._attr_native_step = climate.step
        self._attr_native_unit_of_measurement = _temperature_unit(climate.unit.value)

    async def async_added_to_hass(self) -> None:
        """Keep the temperature chosen before Home Assistant restarted."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is None or last.native_value is None:
            return
        if self._climate.minimum <= last.native_value <= self._climate.maximum:
            self._climate.temperature = last.native_value

    @property
    def native_value(self) -> float:
        """Return the temperature sent with the next start."""
        return self._climate.temperature

    async def async_set_native_value(self, value: float) -> None:
        """Change the temperature sent with the next start."""
        self._climate.temperature = value
        self.async_write_ha_state()
