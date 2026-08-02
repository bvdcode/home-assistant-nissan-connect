"""Sensor entities for MyNISSAN vehicles."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import DistanceUnit, TemperatureUnit, Vehicle, VehicleStatus

from .coordinator import NissanDataUpdateCoordinator
from .entity import NissanEntity
from .models import NissanConfigEntry

type NissanSensorValue = int | float | str | None
type NissanUnit = str | None


@dataclass(frozen=True, kw_only=True)
class NissanSensorEntityDescription(SensorEntityDescription):
    """Describe a MyNISSAN sensor backed by vehicle status."""

    value_fn: Callable[[VehicleStatus], NissanSensorValue]
    unit_fn: Callable[[VehicleStatus], NissanUnit] | None = None


def _climate_temperature(status: VehicleStatus) -> float | None:
    """Return the configured temperature while remote climate is active."""
    if status.climate is None or status.climate.state == "OFF":
        return None
    if status.climate.temperature is None:
        return None
    return status.climate.temperature.value


def _climate_temperature_unit(status: VehicleStatus) -> NissanUnit:
    """Return the configured temperature unit while remote climate is active."""
    if status.climate is None or status.climate.state == "OFF":
        return None
    if status.climate.temperature is None:
        return None
    return _temperature_unit(status.climate.temperature.unit)


BATTERY_SENSOR_DESCRIPTIONS: tuple[NissanSensorEntityDescription, ...] = (
    NissanSensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.battery.level if status.battery is not None else None,
    ),
    NissanSensorEntityDescription(
        key="range",
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: (
            status.battery.remaining_mileage.value
            if status.battery is not None and status.battery.remaining_mileage is not None
            else None
        ),
        unit_fn=lambda status: (
            _distance_unit(status.battery.remaining_mileage.unit)
            if status.battery is not None and status.battery.remaining_mileage is not None
            else None
        ),
    ),
)

CLIMATE_SENSOR_DESCRIPTIONS: tuple[NissanSensorEntityDescription, ...] = (
    NissanSensorEntityDescription(
        key="climate_status",
        translation_key="climate_status",
        value_fn=lambda status: status.climate.state if status.climate is not None else None,
    ),
    NissanSensorEntityDescription(
        key="climate_temperature",
        translation_key="climate_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_climate_temperature,
        unit_fn=_climate_temperature_unit,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MyNISSAN sensors from a config entry."""
    del hass
    coordinator = entry.runtime_data.coordinator
    entities: list[NissanSensor] = []

    for vehicle in entry.runtime_data.vehicles:
        status = coordinator.data[vehicle.vin]
        if status.battery is not None:
            entities.extend(
                NissanSensor(coordinator, vehicle, description)
                for description in BATTERY_SENSOR_DESCRIPTIONS
            )
        if status.climate is not None:
            entities.extend(
                NissanSensor(coordinator, vehicle, description)
                for description in CLIMATE_SENSOR_DESCRIPTIONS
            )

    async_add_entities(entities)


class NissanSensor(NissanEntity, SensorEntity):
    """Represent one value from a vehicle's cached status."""

    entity_description: NissanSensorEntityDescription

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
        description: NissanSensorEntityDescription,
    ) -> None:
        """Initialize a MyNISSAN sensor."""
        self.entity_description = description
        super().__init__(coordinator, vehicle)

    @property
    def available(self) -> bool:
        """Return whether the coordinator has a value for this sensor."""
        return (
            super().available and self.entity_description.value_fn(self.vehicle_status) is not None
        )

    @property
    def native_value(self) -> NissanSensorValue:
        """Return the sensor's current native value."""
        return self.entity_description.value_fn(self.vehicle_status)

    @property
    def native_unit_of_measurement(self) -> NissanUnit:
        """Return the native unit supplied with the vehicle value."""
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.vehicle_status)
        return self.entity_description.native_unit_of_measurement


def _distance_unit(value: str | None) -> NissanUnit:
    """Map a Nissan distance unit to a Home Assistant native unit."""
    match value:
        case DistanceUnit.MILE.value:
            return UnitOfLength.MILES
        case DistanceUnit.KILOMETER.value:
            return UnitOfLength.KILOMETERS
        case None | DistanceUnit.UNKNOWN_VALUE.value:
            return None
        case _:
            return None


def _temperature_unit(value: str) -> NissanUnit:
    """Map a Nissan temperature unit to a Home Assistant native unit."""
    match value:
        case TemperatureUnit.CELSIUS.value:
            return UnitOfTemperature.CELSIUS
        case TemperatureUnit.FAHRENHEIT.value:
            return UnitOfTemperature.FAHRENHEIT
        case TemperatureUnit.UNKNOWN_VALUE.value:
            return None
        case _:
            return None
