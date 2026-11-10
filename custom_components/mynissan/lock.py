"""Remote door lock control for subscribed vehicles."""

import asyncio

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynissan import NissanClient, Vehicle

from .commands import (
    DOOR_LOCK_SERVICES,
    DOOR_UNLOCK_SERVICES,
    NissanCommandEntity,
    supports_service,
)
from .coordinator import NissanDataUpdateCoordinator
from .door_status import door_timestamp_attributes, unlocked_state
from .models import NissanConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a lock when both locking and unlocking are available."""
    del hass
    runtime = entry.runtime_data
    async_add_entities(
        NissanDoorLock(runtime.coordinator, runtime.client, vehicle)
        for vehicle in runtime.vehicles
        if supports_service(runtime.capabilities[vehicle.vin], DOOR_LOCK_SERVICES)
        and supports_service(runtime.capabilities[vehicle.vin], DOOR_UNLOCK_SERVICES)
    )


class NissanDoorLock(NissanCommandEntity, LockEntity):
    """Show command progress while retaining the last reported lock state."""

    entity_description = LockEntityDescription(key="door_lock", translation_key="door_lock")
    _attr_is_locking = False
    _attr_is_unlocking = False

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        client: NissanClient,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the vehicle lock and serialize its commands."""
        super().__init__(coordinator, client, vehicle)
        self._command_lock = asyncio.Lock()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose when the vehicle last reported its lock state."""
        return door_timestamp_attributes(self.vehicle_status)

    @property
    def is_locked(self) -> bool | None:
        """Return the reported overall lock state, or unknown when absent."""
        doors = self.vehicle_status.doors
        unlocked = unlocked_state(doors.overall_lock) if doors else None
        if unlocked is None:
            return None
        return not unlocked

    async def async_lock(self, **kwargs: object) -> None:
        """Lock the doors and wait for command completion."""
        await self._async_set_locked(True)

    async def async_unlock(self, **kwargs: object) -> None:
        """Unlock the doors and wait for command completion."""
        await self._async_set_locked(False)

    async def _async_set_locked(self, locked: bool) -> None:
        async with self._command_lock:
            if locked:
                command = self._client.async_lock_doors
                services = DOOR_LOCK_SERVICES
            else:
                command = self._client.async_unlock_doors
                services = DOOR_UNLOCK_SERVICES
            self._attr_is_locking = locked
            self._attr_is_unlocking = not locked
            self.async_write_ha_state()
            try:
                await self._async_run_command(lambda: command(self._vehicle.vin), services)
            finally:
                self._attr_is_locking = False
                self._attr_is_unlocking = False
                self.async_write_ha_state()
