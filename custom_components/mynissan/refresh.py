"""On-demand refresh of status reported by the vehicle."""

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .commands import NissanCommandEntity
from .const import DOMAIN


class NissanRefreshButton(NissanCommandEntity, ButtonEntity):
    """Request fresh telemetry before reading the updated cloud data."""

    entity_description = ButtonEntityDescription(
        key="refresh",
        translation_key="refresh",
        device_class=ButtonDeviceClass.UPDATE,
        icon="mdi:refresh",
    )

    async def async_press(self) -> None:
        """Wait for fresh vehicle status, then refresh battery and climate data."""
        await self._async_run_command(
            lambda: self._client.async_refresh_vehicle_status(self._vehicle.vin),
            after_success=self._async_refresh_battery_and_climate,
        )

    async def _async_refresh_battery_and_climate(self) -> None:
        if self.vehicle_status.battery is not None and not (
            await self._client.async_refresh_battery_status(self._vehicle.vin)
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=self._command_failed_key
            )
        if self.vehicle_status.climate is not None and not (
            await self._client.async_refresh_climate_status(self._vehicle.vin)
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=self._command_failed_key
            )
