"""On-demand refresh of the vehicle's reported location."""

from homeassistant.components.button import ButtonEntityDescription
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
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
        previous_timestamp = self.vehicle_location.last_updated_at
        if previous_timestamp is None or previous_timestamp.utcoffset() is None:
            previous_timestamp = dt_util.utcnow().replace(microsecond=0)

        def publish_location(result: ServiceRequestResult) -> None:
            location = result.location
            if (
                location is None
                or location.latitude is None
                or location.longitude is None
                or location.last_updated_at is None
                or location.last_updated_at.utcoffset() is None
                or location.last_updated_at <= previous_timestamp
            ):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="location_not_updated"
                )
            self.coordinator.async_set_vehicle_location(location)

        await self._async_run_command(
            lambda: self._client.async_locate_vehicle(self._vehicle.vin),
            LOCATION_SERVICES,
            publish_result=publish_location,
        )
