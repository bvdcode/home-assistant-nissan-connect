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
from pynissan import Vehicle, VehicleCapabilities, VehicleStatus

from .coordinator import NissanDataUpdateCoordinator
from .door_status import door_timestamp_attributes, opening_state, unlocked_state, window_state
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

WINDOW_SENSOR_DESCRIPTIONS: tuple[NissanBinarySensorEntityDescription, ...] = (
    NissanBinarySensorEntityDescription(
        key="window_front_left",
        translation_key="window_front_left",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda s: (
            window_state(s.doors.front_left.window) if s.doors and s.doors.front_left else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="window_front_right",
        translation_key="window_front_right",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda s: (
            window_state(s.doors.front_right.window) if s.doors and s.doors.front_right else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="window_rear_left",
        translation_key="window_rear_left",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda s: (
            window_state(s.doors.rear_left.window) if s.doors and s.doors.rear_left else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="window_rear_right",
        translation_key="window_rear_right",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda s: (
            window_state(s.doors.rear_right.window) if s.doors and s.doors.rear_right else None
        ),
    ),
    NissanBinarySensorEntityDescription(
        key="sunroof",
        translation_key="sunroof",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda s: window_state(s.doors.sunroof_ajar) if s.doors else None,
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
        if status.battery is not None:
            entities.extend(
                NissanBinarySensor(coordinator, vehicle, description)
                for description in BINARY_SENSOR_DESCRIPTIONS
            )
        if status.doors is not None:
            entities.extend(
                NissanDoorBinarySensor(coordinator, vehicle, description)
                for description in DOOR_SENSOR_DESCRIPTIONS
            )
        entities.extend(
            NissanDoorBinarySensor(coordinator, vehicle, description)
            for description in WINDOW_SENSOR_DESCRIPTIONS
            if _supports_window_sensor(entry.runtime_data.capabilities[vehicle.vin], description)
            or description.value_fn(status) is not None
        )
    async_add_entities(entities)


def _supports_window_sensor(
    capabilities: VehicleCapabilities,
    description: NissanBinarySensorEntityDescription,
) -> bool:
    """Retain advertised window sensors while their initial readings are unavailable."""
    details = capabilities.accessories_details
    if details is None:
        return False
    match description.key:
        case "sunroof":
            return details.sun_roof is not None and details.sun_roof.enabled is True
        case "window_front_left" | "window_front_right" | "window_rear_left" | "window_rear_right":
            return details.window_status is not None and details.window_status.enabled is True
        case _:
            raise ValueError(f"Unsupported window sensor: {description.key}")


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


class NissanDoorBinarySensor(NissanBinarySensor):
    """Represent an opening or lock with its reported observation time."""

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return the vehicle's door-status timestamp when provided."""
        return door_timestamp_attributes(self.vehicle_status)
