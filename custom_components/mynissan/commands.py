"""Shared execution and capability checks for remote vehicle commands."""

from collections.abc import Awaitable, Callable

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pynissan import NissanClient, NissanError, ServiceRequest, Vehicle, VehicleCapabilities

from .const import DOMAIN
from .coordinator import NissanDataUpdateCoordinator
from .entity import NissanEntity

DOOR_LOCK_SERVICES = ("REMOTE_DOOR_LOCK_UNLOCK", "REMOTE_DOOR_LOCK")
DOOR_UNLOCK_SERVICES = ("REMOTE_DOOR_LOCK_UNLOCK", "REMOTE_DOOR_UNLOCK")
HORN_LIGHTS_SERVICES = ("REMOTE_HORN_LIGHTS",)
ENGINE_SERVICES = ("REMOTE_ENGINE",)


def supports_service(capabilities: VehicleCapabilities, services: tuple[str, ...]) -> bool:
    """Require an explicitly enabled service with a confirmed subscription."""
    return any(
        service.type in services and service.enabled and service.subscribed is True
        for service in capabilities.services
    )


class NissanCommandEntity(NissanEntity):
    """Wait for remote command completion before refreshing reported status."""

    _command_failed_key = "command_failed"
    _command_rejected_key = "command_rejected"

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        client: NissanClient,
        vehicle: Vehicle,
    ) -> None:
        """Initialize a vehicle command entity."""
        super().__init__(coordinator, vehicle)
        self._client = client

    async def _async_run_command(
        self,
        command: Callable[[], Awaitable[ServiceRequest]],
        services: tuple[str, ...] = (),
        *,
        after_success: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        try:
            if services:
                capabilities = await self._client.async_get_vehicle_capabilities(
                    self._vehicle.vin, self.coordinator.temperature_unit
                )
                if not supports_service(capabilities, services):
                    raise ServiceValidationError(
                        translation_domain=DOMAIN, translation_key="command_not_supported"
                    )
            request = await command()
            result = await self._client.async_wait_for_service_request(self._vehicle.vin, request)
            if not result.is_success:
                status = result.status.value if result.status is not None else "unknown"
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=self._command_rejected_key,
                    translation_placeholders={
                        "status": status,
                        "details": result.status_details or "unknown",
                    },
                )
            if after_success is not None:
                await after_success()
        except (NissanError, TimeoutError) as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=self._command_failed_key
            ) from error
        await self.coordinator.async_request_refresh()
