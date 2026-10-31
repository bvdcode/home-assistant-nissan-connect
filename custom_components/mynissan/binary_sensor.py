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
from .door_status import opening_state, unlocked_state
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

DOOR_SENSOR_DESCRIPTIONS: tuple[NissanBinarySensorEntityDescription, ...] = (
    NissanBinarySensorEntityDescription(
        key="door_front_left",
        translation_key="door_front_left",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda s: (
            opening_state(s.doors.front_left.ajar) if s.doors and s.doors.front_left else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="door_front_left_unlocked",
        translation_key="door_front_left_unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda s: (
            unlocked_state(s.doors.front_left.lock) if s.doors and s.doors.front_left else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="door_front_right",
        translation_key="door_front_right",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda s: (
            opening_state(s.doors.front_right.ajar) if s.doors and s.doors.front_right else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="door_front_right_unlocked",
        translation_key="door_front_right_unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda s: (
            unlocked_state(s.doors.front_right.lock) if s.doors and s.doors.front_right else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="door_rear_left",
        translation_key="door_rear_left",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda s: (
            opening_state(s.doors.rear_left.ajar) if s.doors and s.doors.rear_left else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="door_rear_left_unlocked",
        translation_key="door_rear_left_unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda s: (
            unlocked_state(s.doors.rear_left.lock) if s.doors and s.doors.rear_left else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="door_rear_right",
        translation_key="door_rear_right",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda s: (
            opening_state(s.doors.rear_right.ajar) if s.doors and s.doors.rear_right else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="door_rear_right_unlocked",
        translation_key="door_rear_right_unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda s: (
            unlocked_state(s.doors.rear_right.lock) if s.doors and s.doors.rear_right else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="hood",
        translation_key="hood",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda s: opening_state(s.doors.engine_hood_ajar) if s.doors else None,
    ),
    NissanBinarySensorEntityDescription(
        key="hatch",
        translation_key="hatch",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda s: opening_state(s.doors.hatch_ajar) if s.doors else None,
    ),
    NissanBinarySensorEntityDescription(
        key="doors_unlocked",
        translation_key="doors_unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda s: unlocked_state(s.doors.overall_lock) if s.doors else None,
    ),
    NissanBinarySensorEntityDescription(
        key="trunk_unlocked",
        translation_key="trunk_unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda s: unlocked_state(s.doors.trunk_lock) if s.doors else None,
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
    entities: list[NissanBinarySensor] = []
    for vehicle in entry.runtime_data.vehicles:
        status = coordinator.data[vehicle.vin].status
        descriptions: tuple[NissanBinarySensorEntityDescription, ...] = ()
        if status.battery is not None:
            descriptions += BINARY_SENSOR_DESCRIPTIONS
        if status.doors is not None:
            descriptions += DOOR_SENSOR_DESCRIPTIONS
        entities.extend(
            NissanBinarySensor(coordinator, vehicle, description) for description in descriptions
        )
    async_add_entities(entities)


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
