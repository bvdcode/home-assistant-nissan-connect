"""On-demand refresh of the vehicle's reported location."""

from homeassistant.components.button import ButtonEntityDescription
from homeassistant.exceptions import HomeAssistantError
from pynissan import ServiceRequestResult

from .command_button import NissanButtonEntity
from .const import DOMAIN

LOCATION_SERVICES = ("PARKED_CAR_FINDER",)


class NissanLocationRefreshButton(NissanButtonEntity):
    """Locate the vehicle and publish the coordinates returned by Nissan."""

    entity_description = ButtonEntityDescription(
        key="refresh_location",
        translation_key="refresh_location",
        icon="mdi:map-marker-refresh",
    )

    async def async_press(self) -> None:
        """Request a location and verify that Nissan reports a fresh fix."""
        previous_location = self.vehicle_location

        async def publish_location(result: ServiceRequestResult) -> None:
            if not self.coordinator.async_publish_vehicle_location(
                previous_location, result.location
            ):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="location_not_updated"
                )

        await self._async_run_command(
            lambda: self._client.async_locate_vehicle(self._vehicle.vin),
            LOCATION_SERVICES,
            handle_result=publish_location,
        )
