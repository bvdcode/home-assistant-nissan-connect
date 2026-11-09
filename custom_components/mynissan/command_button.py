"""Shared progress icon for remote vehicle command buttons."""

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from pynissan import NissanClient, ServiceRequest, Vehicle

from .commands import NissanCommandEntity
from .coordinator import NissanDataUpdateCoordinator

PENDING_COMMAND_ICON = "mdi:timer-sand"


class NissanButtonEntity(NissanCommandEntity, ButtonEntity):
    """Show an hourglass until all active button commands have finished."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        client: NissanClient,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the button's active command count."""
        super().__init__(coordinator, client, vehicle)
        self._commands_in_progress: int = 0

    @property
    def icon(self) -> str | None:
        """Return an hourglass while a command is pending, otherwise the normal icon."""
        if self._commands_in_progress:
            return PENDING_COMMAND_ICON
        return super().icon

    async def _async_run_command(
        self,
        command: Callable[[], Awaitable[ServiceRequest]],
        services: tuple[str, ...] = (),
        *,
        after_success: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._commands_in_progress += 1
        self.async_write_ha_state()
        try:
            await super()._async_run_command(command, services, after_success=after_success)
        finally:
            self._commands_in_progress -= 1
            self.async_write_ha_state()
