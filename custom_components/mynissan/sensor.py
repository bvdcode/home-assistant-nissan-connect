"""Sensor entities for MyNISSAN vehicles."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import DistanceUnit, TemperatureUnit, Vehicle, VehicleStatus

from .charge_completion import NissanChargeCompletionSensor, remaining_charge_minutes
from .coordinator import NissanDataUpdateCoordinator
from .entity import NissanEntity
from .models import NissanConfigEntry
from .timestamps import timestamp_attributes

type NissanSensorValue = int | float | str | None
type NissanUnit = str | None


@dataclass(frozen=True, kw_only=True)
class NissanSensorEntityDescription(SensorEntityDescription):
    """Describe a MyNISSAN sensor backed by vehicle status."""

    value_fn: Callable[[VehicleStatus], NissanSensorValue]
    unit_fn: Callable[[VehicleStatus], NissanUnit] | None = None
    attributes_fn: Callable[[VehicleStatus], dict[str, object] | None] | None = None
    last_updated_fn: Callable[[VehicleStatus], datetime | None] | None = None


def _climate_temperature(status: VehicleStatus) -> float | None:
    """Return the reported cabin temperature."""
    if status.climate is None or status.climate.temperature is None:
        return None
    return status.climate.temperature.value


def _climate_temperature_unit(status: VehicleStatus) -> NissanUnit:
    """Return the reported cabin temperature unit."""
    if status.climate is None or status.climate.temperature is None:
        return None
    return _temperature_unit(status.climate.temperature.unit)


BATTERY_SENSOR_DESCRIPTIONS: tuple[NissanSensorEntityDescription, ...] = (
    NissanSensorEntityDescription(
        key="remaining_charge_time",
        translation_key="remaining_charge_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=remaining_charge_minutes,
    ),
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

ODOMETER_DESCRIPTION = NissanSensorEntityDescription(
    key="odometer",
    translation_key="odometer",
    device_class=SensorDeviceClass.DISTANCE,
    state_class=SensorStateClass.TOTAL_INCREASING,
    value_fn=lambda status: status.mileage.total if status.mileage is not None else None,
    unit_fn=lambda status: _distance_unit(status.mileage.unit) if status.mileage else None,
    last_updated_fn=lambda status: status.mileage.recorded_at if status.mileage else None,
)

TIRE_SENSOR_DESCRIPTIONS: tuple[NissanSensorEntityDescription, ...] = tuple(
    NissanSensorEntityDescription(
        key=f"tire_pressure_{position}",
        translation_key=f"tire_pressure_{position}",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
        last_updated_fn=lambda status: (
            status.tire_pressure.last_updated_at if status.tire_pressure else None
        ),
    )
    for position, value_fn, attributes_fn in (
        (
            "front_left",
            lambda s: s.tire_pressure.front_left if s.tire_pressure else None,
            lambda s: {"status": s.tire_pressure.front_left_status} if s.tire_pressure else None,
        ),
        (
            "front_right",
            lambda s: s.tire_pressure.front_right if s.tire_pressure else None,
            lambda s: {"status": s.tire_pressure.front_right_status} if s.tire_pressure else None,
        ),
        (
            "rear_left",
            lambda s: s.tire_pressure.rear_left if s.tire_pressure else None,
            lambda s: {"status": s.tire_pressure.rear_left_status} if s.tire_pressure else None,
        ),
        (
            "rear_right",
            lambda s: s.tire_pressure.rear_right if s.tire_pressure else None,
            lambda s: {"status": s.tire_pressure.rear_right_status} if s.tire_pressure else None,
        ),
    )
)

WARNINGS_DESCRIPTION = NissanSensorEntityDescription(
    key="warnings",
    translation_key="warnings",
    icon="mdi:alert-circle-outline",
    value_fn=lambda status: sum(item.active is True for item in status.maintenance_indicators),
    attributes_fn=lambda status: {
        "warnings": [
            {"type": item.type, "message": item.detailed_message}
            for item in status.maintenance_indicators
            if item.active is True
        ]
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MyNISSAN sensors from a config entry."""
    del hass
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []

    for vehicle in entry.runtime_data.vehicles:
        status = coordinator.data[vehicle.vin].status
        if status.battery is not None:
            entities.append(NissanChargeCompletionSensor(coordinator, vehicle))
            entities.extend(
                NissanSensor(coordinator, vehicle, description)
                for description in BATTERY_SENSOR_DESCRIPTIONS
            )
        if status.climate is not None:
            entities.extend(
                NissanSensor(coordinator, vehicle, description)
                for description in CLIMATE_SENSOR_DESCRIPTIONS
            )
        if status.mileage is not None:
            entities.append(NissanSensor(coordinator, vehicle, ODOMETER_DESCRIPTION))
        if status.tire_pressure is not None:
            entities.extend(
                NissanSensor(coordinator, vehicle, description)
                for description in TIRE_SENSOR_DESCRIPTIONS
            )
        entities.append(NissanSensor(coordinator, vehicle, WARNINGS_DESCRIPTION))

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

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Expose reported timestamps, tire status, and active warnings."""
        attributes: dict[str, object] = {}
        if self.entity_description.attributes_fn is not None:
            reported_attributes = self.entity_description.attributes_fn(self.vehicle_status)
            if reported_attributes is not None:
                attributes.update(reported_attributes)
        if self.entity_description.last_updated_fn is not None:
            attributes.update(
                timestamp_attributes(self.entity_description.last_updated_fn(self.vehicle_status))
            )
        return attributes or None


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
