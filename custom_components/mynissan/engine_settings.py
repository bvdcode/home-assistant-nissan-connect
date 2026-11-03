"""Base entity for remote start climate settings kept in Home Assistant."""

from homeassistant.const import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from pynissan import Vehicle

from .coordinator import NissanDataUpdateCoordinator
from .engine_climate import EngineClimate
from .entity import NissanEntity


class NissanEngineSetting(NissanEntity, RestoreEntity):
    """Edit one value of the climate request sent with each remote engine start."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
        climate: EngineClimate,
    ) -> None:
        """Initialize a setting backed by the vehicle's shared climate request."""
        super().__init__(coordinator, vehicle)
        self._climate = climate
