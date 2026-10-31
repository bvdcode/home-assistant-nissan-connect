"""Remote door lock control for subscribed vehicles."""

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .commands import (
    DOOR_LOCK_SERVICES,
    DOOR_UNLOCK_SERVICES,
    NissanCommandEntity,
    supports_service,
)
from .door_status import unlocked_state
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
    """Control the door locks while retaining the last reported lock state."""

    entity_description = LockEntityDescription(key="door_lock", translation_key="door_lock")

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
        await self._async_run_command(
            lambda: self._client.async_lock_doors(self._vehicle.vin), DOOR_LOCK_SERVICES
        )

    async def async_unlock(self, **kwargs: object) -> None:
        """Unlock the doors and wait for command completion."""
        await self._async_run_command(
            lambda: self._client.async_unlock_doors(self._vehicle.vin), DOOR_UNLOCK_SERVICES
        )
