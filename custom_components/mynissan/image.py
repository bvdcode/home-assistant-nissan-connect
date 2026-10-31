"""Vehicle artwork supplied by MyNISSAN."""

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from pynissan import Vehicle

from .coordinator import NissanDataUpdateCoordinator
from .entity import NissanEntity
from .models import NissanConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add artwork for vehicles that supply an image URL."""
    async_add_entities(
        NissanVehicleImage(hass, entry.runtime_data.coordinator, vehicle)
        for vehicle in entry.runtime_data.vehicles
        if vehicle.image_url
    )


class NissanVehicleImage(NissanEntity, ImageEntity):
    """Display the account's vehicle image through Home Assistant's image proxy."""

    entity_description = ImageEntityDescription(key="vehicle", translation_key="vehicle")

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the image using a TLS-verifying client without account tokens."""
        NissanEntity.__init__(self, coordinator, vehicle)
        ImageEntity.__init__(self, hass, verify_ssl=True)
        self._attr_image_url = vehicle.image_url
        self._attr_image_last_updated = dt_util.utcnow()
