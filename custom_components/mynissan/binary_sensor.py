"""Binary sensor entities for MyNISSAN vehicles."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import Vehicle, VehicleStatus

from .coordinator import NissanDataUpdateCoordinator
from .entity import NissanEntity
from .models import NissanConfigEntry


@dataclass(frozen=True, kw_only=True)
class NissanBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a MyNISSAN binary sensor backed by vehicle status."""

    value_fn: Callable[[VehicleStatus], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[NissanBinarySensorEntityDescription, ...] = (
    NissanBinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda status: status.battery.is_charging if status.battery is not None else None,
    ),
    NissanBinarySensorEntityDescription(
        key="plugged_in",
        translation_key="plugged_in",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda status: (
            status.battery.is_plugged_in if status.battery is not None else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MyNISSAN binary sensors from a config entry."""
    del hass
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        NissanBinarySensor(coordinator, vehicle, description)
        for vehicle in entry.runtime_data.vehicles
        if coordinator.data[vehicle.vin].battery is not None
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class NissanBinarySensor(NissanEntity, BinarySensorEntity):
    """Represent one boolean value from a vehicle's cached status."""

    entity_description: NissanBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
        description: NissanBinarySensorEntityDescription,
    ) -> None:
        """Initialize a MyNISSAN binary sensor."""
        self.entity_description = description
        super().__init__(coordinator, vehicle)

    @property
    def available(self) -> bool:
        """Return whether the coordinator has a value for this sensor."""
        return (
            super().available and self.entity_description.value_fn(self.vehicle_status) is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return the sensor's current boolean value."""
        return self.entity_description.value_fn(self.vehicle_status)
