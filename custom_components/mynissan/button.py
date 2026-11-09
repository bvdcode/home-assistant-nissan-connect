"""Vehicle refresh and capability-gated command buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import NissanClient, SeatClimateOption, ServiceRequest, Vehicle

from .command_button import NissanButtonEntity
from .commands import (
    DOOR_LOCK_SERVICES,
    DOOR_UNLOCK_SERVICES,
    ENGINE_SERVICES,
    HORN_LIGHTS_SERVICES,
    supports_service,
)
from .const import ENGINE_START_EVENT, ENGINE_STOP_EVENT, SIGNAL_ENGINE_COMMAND
from .coordinator import NissanDataUpdateCoordinator
from .engine_climate import EngineClimate
from .models import NissanConfigEntry
from .refresh import NissanRefreshButton


@dataclass(frozen=True, kw_only=True)
class NissanButtonDescription(ButtonEntityDescription):
    """Describe a command and the subscription needed to execute it."""

    services: tuple[str, ...]
    command: Callable[[NissanClient, str], Awaitable[ServiceRequest]]
    excluded_services: tuple[str, ...] = ()
    rejected_key: str = "command_rejected"
    engine_event: str | None = None


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
    # Sends the climate settings chosen in Home Assistant when the vehicle supports them.
    NissanButtonDescription(
        key="remote_engine_start",
        translation_key="remote_engine_start",
        icon="mdi:car-key",
        services=ENGINE_SERVICES,
        rejected_key="engine_command_rejected",
        engine_event=ENGINE_START_EVENT,
        command=lambda client, vin: client.async_start_engine(vin),
    ),
    NissanButtonDescription(
        key="remote_engine_stop",
        translation_key="remote_engine_stop",
        icon="mdi:car-off",
        services=ENGINE_SERVICES,
        rejected_key="engine_command_rejected",
        engine_event=ENGINE_STOP_EVENT,
        command=lambda client, vin: client.async_stop_engine(vin),
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
    for vehicle in runtime.vehicles:
        for description in BUTTON_DESCRIPTIONS:
            capabilities = runtime.capabilities[vehicle.vin]
            if not supports_service(capabilities, description.services) or supports_service(
                capabilities, description.excluded_services
            ):
                continue
            if description.key == "remote_engine_start":
                entities.append(
                    NissanEngineStartButton(
                        runtime.coordinator,
                        runtime.client,
                        vehicle,
                        description,
                        runtime.engine_climate.get(vehicle.vin),
                    )
                )
            else:
                entities.append(
                    NissanCommandButton(runtime.coordinator, runtime.client, vehicle, description)
                )
    async_add_entities(entities)


class NissanCommandButton(NissanButtonEntity):
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
        self._command_rejected_key = description.rejected_key
        super().__init__(coordinator, client, vehicle)

    async def async_press(self) -> None:
        """Send the command and wait for its result."""
        await self._async_run_command(
            lambda: self.entity_description.command(self._client, self._vehicle.vin),
            self.entity_description.services,
            after_success=self._async_announce,
        )

    async def _async_announce(self) -> None:
        """Tell the last start and stop sensors that an engine command completed."""
        if self.entity_description.engine_event is not None:
            async_dispatcher_send(
                self.hass,
                SIGNAL_ENGINE_COMMAND.format(self._vehicle.vin),
                self.entity_description.engine_event,
            )


class NissanEngineStartButton(NissanCommandButton):
    """Start the engine with the climate settings chosen in Home Assistant."""

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        client: NissanClient,
        vehicle: Vehicle,
        description: NissanButtonDescription,
        climate: EngineClimate | None,
    ) -> None:
        """Initialize the start button with the vehicle's climate options."""
        super().__init__(coordinator, client, vehicle, description)
        self.climate = climate

    async def async_press(self) -> None:
        """Start the engine with the current climate settings."""
        await self.async_start_engine()

    async def async_start_engine(
        self,
        *,
        temperature: float | None = None,
        seats: dict[str, SeatClimateOption] | None = None,
        steering_wheel_heater: bool | None = None,
        defrost: bool | None = None,
    ) -> None:
        """Start the engine, overriding individual climate settings for this start only."""
        climate = (
            None
            if self.climate is None
            else self.climate.settings(
                temperature=temperature,
                seats=seats,
                steering_wheel_heater=steering_wheel_heater,
                defrost=defrost,
            )
        )
        await self._async_run_command(
            lambda: self._client.async_start_engine(self._vehicle.vin, climate=climate),
            self.entity_description.services,
            after_success=self._async_announce,
        )
