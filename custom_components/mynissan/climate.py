"""Climate control entities for MyNISSAN vehicles."""

from collections.abc import Awaitable
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
)
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import (
    ClimateSettings,
    HvacTemperatureCapabilities,
    NissanClient,
    NissanError,
    ServiceRequest,
    TemperatureUnit,
    Vehicle,
    VehicleCapabilities,
)

from .const import DOMAIN
from .coordinator import NissanDataUpdateCoordinator
from .entity import NissanEntity
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


class NissanClimate(NissanEntity, ClimateEntity):
    """Control a vehicle's remote cabin climate system."""

    entity_description = CLIMATE_DESCRIPTION

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        client: NissanClient,
        vehicle: Vehicle,
        temperatures: HvacTemperatureCapabilities,
    ) -> None:
        """Initialize a MyNISSAN climate control."""
        super().__init__(coordinator, vehicle)
        self._client = client
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
        """Return the active or most recently selected target temperature."""
        climate = self.vehicle_status.climate
        if climate is not None and climate.state == "ON" and climate.temperature is not None:
            return climate.temperature.value
        return self._target_temperature

    async def async_turn_on(self) -> None:
        """Start remote climate control."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return
        await self._async_run_command(
            self._client.async_start_climate(
                self._vehicle.vin,
                self._settings(self._target_temperature),
            )
        )

    async def async_turn_off(self) -> None:
        """Stop remote climate control."""
        if self.hvac_mode == HVACMode.OFF:
            return
        await self._async_run_command(self._client.async_stop_climate(self._vehicle.vin))

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
                self._client.async_adjust_climate(
                    self._vehicle.vin,
                    self._settings(self._target_temperature),
                )
            )
            return
        self.async_write_ha_state()

    def _settings(self, temperature: float) -> ClimateSettings:
        return ClimateSettings(temperature, self._nissan_temperature_unit)

    async def _async_run_command(self, command: Awaitable[ServiceRequest]) -> None:
        try:
            request = await command
            result = await self._client.async_wait_for_service_request(
                self._vehicle.vin,
                request,
            )
        except (NissanError, TimeoutError) as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="climate_command_failed",
            ) from error

        if not result.is_success:
            status = result.status.value if result.status is not None else "unknown"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="climate_command_rejected",
                translation_placeholders={"status": status},
            )
        await self.coordinator.async_request_refresh()


def _climate_temperatures(
    capabilities: VehicleCapabilities,
) -> HvacTemperatureCapabilities | None:
    """Return HVAC temperatures when remote climate is enabled and subscribed."""
    climate_enabled = any(
        service.type == "CLIMATE_CONTROL" and service.enabled and service.subscribed is True
        for service in capabilities.services
    )
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
