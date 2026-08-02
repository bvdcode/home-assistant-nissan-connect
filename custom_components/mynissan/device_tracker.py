"""Device trackers for MyNISSAN vehicles."""

from homeassistant.components.device_tracker.entity import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import NissanEntity
from .models import NissanConfigEntry

LOCATION_DESCRIPTION = TrackerEntityDescription(
    key="location",
    translation_key="location",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MyNISSAN vehicle trackers."""
    del hass
    runtime_data = entry.runtime_data
    async_add_entities(
        NissanVehicleTracker(runtime_data.coordinator, vehicle) for vehicle in runtime_data.vehicles
    )


class NissanVehicleTracker(NissanEntity, TrackerEntity):
    """Represent a vehicle's last reported location."""

    entity_description = LOCATION_DESCRIPTION

    @property
    def available(self) -> bool:
        """Return whether the vehicle has a reported location."""
        return (
            super().available
            and self.vehicle_location.latitude is not None
            and self.vehicle_location.longitude is not None
        )

    @property
    def latitude(self) -> float | None:
        """Return the vehicle latitude."""
        return self.vehicle_location.latitude

    @property
    def longitude(self) -> float | None:
        """Return the vehicle longitude."""
        return self.vehicle_location.longitude
