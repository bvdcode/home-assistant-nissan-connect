"""Vehicle refresh and capability-gated command buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import NissanClient, ServiceRequest, Vehicle

from .commands import (
    DOOR_LOCK_SERVICES,
    DOOR_UNLOCK_SERVICES,
    HORN_LIGHTS_SERVICES,
    NissanCommandEntity,
    supports_service,
)
from .coordinator import NissanDataUpdateCoordinator
from .models import NissanConfigEntry
from .refresh import NissanRefreshButton


@dataclass(frozen=True, kw_only=True)
class NissanButtonDescription(ButtonEntityDescription):
    """Describe a command and the subscription needed to execute it."""

    services: tuple[str, ...]
    command: Callable[[NissanClient, str], Awaitable[ServiceRequest]]
    excluded_services: tuple[str, ...] = ()


BUTTON_DESCRIPTIONS = (
    NissanButtonDescription(
        key="flash_lights",
        translation_key="flash_lights",
        icon="mdi:car-light-high",
        services=HORN_LIGHTS_SERVICES,
        command=lambda client, vin: client.async_flash_lights(vin),
    ),
    NissanButtonDescription(
        key="flash_lights_and_horn",
        translation_key="flash_lights_and_horn",
        icon="mdi:bullhorn",
        services=HORN_LIGHTS_SERVICES,
        command=lambda client, vin: client.async_flash_lights_and_horn(vin),
    ),
    NissanButtonDescription(
        key="lock_doors",
        translation_key="lock_doors",
        icon="mdi:lock",
        services=DOOR_LOCK_SERVICES,
        excluded_services=DOOR_UNLOCK_SERVICES,
        command=lambda client, vin: client.async_lock_doors(vin),
    ),
    NissanButtonDescription(
        key="unlock_doors",
        translation_key="unlock_doors",
        icon="mdi:lock-open",
        services=DOOR_UNLOCK_SERVICES,
        excluded_services=DOOR_LOCK_SERVICES,
        command=lambda client, vin: client.async_unlock_doors(vin),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose on-demand refresh and supported remote commands."""
    del hass
    runtime = entry.runtime_data
    entities: list[ButtonEntity] = [
        NissanRefreshButton(runtime.coordinator, runtime.client, vehicle)
        for vehicle in runtime.vehicles
    ]
    entities.extend(
        NissanCommandButton(runtime.coordinator, runtime.client, vehicle, description)
        for vehicle in runtime.vehicles
        for description in BUTTON_DESCRIPTIONS
        if supports_service(runtime.capabilities[vehicle.vin], description.services)
        and not supports_service(runtime.capabilities[vehicle.vin], description.excluded_services)
    )
    async_add_entities(entities)


class NissanCommandButton(NissanCommandEntity, ButtonEntity):
    """Send one vehicle command when explicitly pressed."""

    entity_description: NissanButtonDescription

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        client: NissanClient,
        vehicle: Vehicle,
        description: NissanButtonDescription,
    ) -> None:
        """Initialize the command button."""
        self.entity_description = description
        super().__init__(coordinator, client, vehicle)

    async def async_press(self) -> None:
        """Send the command and wait for its result."""
        await self._async_run_command(
            lambda: self.entity_description.command(self._client, self._vehicle.vin),
            self.entity_description.services,
        )
