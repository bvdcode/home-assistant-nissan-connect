"""Base entity for MyNISSAN vehicles."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pynissan import Vehicle, VehicleLocation, VehicleStatus

from .const import DOMAIN
from .coordinator import NissanDataUpdateCoordinator


class NissanEntity(CoordinatorEntity[NissanDataUpdateCoordinator]):
    """Represent an entity belonging to one MyNISSAN vehicle."""

    _attr_has_entity_name = True
    entity_description: EntityDescription

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize a vehicle entity."""
        super().__init__(coordinator)
        self._vehicle = vehicle
        self._attr_unique_id = f"{vehicle.vin}_{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the vehicle device associated with this entity."""
        return DeviceInfo(identifiers={(DOMAIN, self._vehicle.vin)})

    @property
    def vehicle_status(self) -> VehicleStatus:
        """Return this vehicle's latest coordinator data."""
        return self.coordinator.data[self._vehicle.vin].status

    @property
    def vehicle_location(self) -> VehicleLocation:
        """Return this vehicle's latest cached location."""
        return self.coordinator.data[self._vehicle.vin].location
