"""Climate control entities for MyNISSAN vehicles."""

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
)
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import (
    ClimateSettings,
    HvacTemperatureCapabilities,
    NissanClient,
    TemperatureUnit,
    Vehicle,
    VehicleCapabilities,
)

from .commands import NissanCommandEntity, supports_service
from .const import DOMAIN, REMOTE_CLIMATE_CONTROL_SERVICE
from .coordinator import NissanDataUpdateCoordinator
from .models import NissanConfigEntry

CLIMATE_DESCRIPTION = ClimateEntityDescription(
    key="climate_control",
    translation_key="climate_control",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up supported MyNISSAN climate controls."""
    del hass
    runtime_data = entry.runtime_data
    entities: list[NissanClimate] = []
    for vehicle in runtime_data.vehicles:
        capabilities = runtime_data.capabilities[vehicle.vin]
        temperatures = _climate_temperatures(capabilities)
        if temperatures is not None:
            entities.append(
                NissanClimate(
                    runtime_data.coordinator,
                    runtime_data.client,
                    vehicle,
                    temperatures,
                )
            )

    async_add_entities(entities)


class NissanClimate(NissanCommandEntity, ClimateEntity):
    """Control a vehicle's remote cabin climate system."""

    entity_description = CLIMATE_DESCRIPTION
    _command_failed_key = "climate_command_failed"
    _command_rejected_key = "climate_command_rejected"

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        client: NissanClient,
        vehicle: Vehicle,
        temperatures: HvacTemperatureCapabilities,
    ) -> None:
        """Initialize a MyNISSAN climate control."""
        super().__init__(coordinator, client, vehicle)
        self._attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        self._nissan_temperature_unit = _nissan_temperature_unit(temperatures.unit)
        self._attr_temperature_unit = _temperature_unit(temperatures.unit)
        self._attr_min_temp = temperatures.minimum
        self._attr_max_temp = temperatures.maximum
        self._attr_target_temperature_step = temperatures.resolution
        self._target_temperature = temperatures.default

    @property
    def available(self) -> bool:
        """Return whether climate status is available for this vehicle."""
        return super().available and self.vehicle_status.climate is not None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current remote climate mode."""
        climate = self.vehicle_status.climate
        if climate is None:
            return None
        match climate.state:
            case "ON":
                return HVACMode.HEAT_COOL
            case "OFF":
                return HVACMode.OFF
            case _:
                return None

    @property
    def target_temperature(self) -> float:
        """Return the most recently selected target temperature."""
        return self._target_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the reported cabin temperature."""
        climate = self.vehicle_status.climate
        if climate is None or climate.temperature is None:
            return None
        return climate.temperature.value

    async def async_turn_on(self) -> None:
        """Start remote climate control."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return
        await self._async_run_command(
            lambda: self._client.async_start_climate(
                self._vehicle.vin,
                self._settings(self._target_temperature),
            )
        )

    async def async_turn_off(self) -> None:
        """Stop remote climate control."""
        if self.hvac_mode == HVACMode.OFF:
            return
        await self._async_run_command(lambda: self._client.async_stop_climate(self._vehicle.vin))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Start or stop remote climate control."""
        match hvac_mode:
            case HVACMode.HEAT_COOL:
                await self.async_turn_on()
            case HVACMode.OFF:
                await self.async_turn_off()
            case _:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_hvac_mode",
                    translation_placeholders={"mode": hvac_mode.value},
                )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature and adjust active climate control."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if not isinstance(temperature, int | float):
            return

        self._target_temperature = float(temperature)
        if self.hvac_mode == HVACMode.HEAT_COOL:
            await self._async_run_command(
                lambda: self._client.async_adjust_climate(
                    self._vehicle.vin,
                    self._settings(self._target_temperature),
                )
            )
            return
        self.async_write_ha_state()

    def _settings(self, temperature: float) -> ClimateSettings:
        return ClimateSettings(temperature, self._nissan_temperature_unit)


def _climate_temperatures(
    capabilities: VehicleCapabilities,
) -> HvacTemperatureCapabilities | None:
    """Return HVAC temperatures when remote climate is enabled and subscribed."""
    climate_enabled = supports_service(capabilities, (REMOTE_CLIMATE_CONTROL_SERVICE,))
    if not climate_enabled or capabilities.accessories_details is None:
        return None
    return capabilities.accessories_details.hvac_temperatures


def _temperature_unit(unit: str) -> UnitOfTemperature:
    match unit:
        case TemperatureUnit.CELSIUS.value:
            return UnitOfTemperature.CELSIUS
        case TemperatureUnit.FAHRENHEIT.value:
            return UnitOfTemperature.FAHRENHEIT
        case _:
            raise ValueError(f"Unsupported climate temperature unit: {unit}")


def _nissan_temperature_unit(unit: str) -> TemperatureUnit:
    match unit:
        case TemperatureUnit.CELSIUS.value:
            return TemperatureUnit.CELSIUS
        case TemperatureUnit.FAHRENHEIT.value:
            return TemperatureUnit.FAHRENHEIT
        case _:
            raise ValueError(f"Unsupported climate temperature unit: {unit}")
