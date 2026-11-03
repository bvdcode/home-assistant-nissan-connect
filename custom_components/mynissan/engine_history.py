"""When Home Assistant last started or stopped the engine remotely."""

from datetime import datetime

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from pynissan import Vehicle

from .const import ENGINE_START_EVENT, ENGINE_STOP_EVENT, SIGNAL_ENGINE_COMMAND
from .coordinator import NissanDataUpdateCoordinator
from .entity import NissanEntity

# The vehicle does not report whether the engine is running, so these record
# successful commands sent from Home Assistant (not starts from the app or key fob).
ENGINE_HISTORY_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    ENGINE_START_EVENT: SensorEntityDescription(
        key="last_remote_engine_start",
        translation_key="last_remote_engine_start",
        icon="mdi:car-key",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ENGINE_STOP_EVENT: SensorEntityDescription(
        key="last_remote_engine_stop",
        translation_key="last_remote_engine_stop",
        icon="mdi:car-off",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
}


class NissanEngineHistorySensor(NissanEntity, RestoreSensor):
    """Record the time of the last successful remote start or stop."""

    entity_description: SensorEntityDescription
    _attr_native_value: datetime | None = None

    def __init__(
        self,
        coordinator: NissanDataUpdateCoordinator,
        vehicle: Vehicle,
        event: str,
    ) -> None:
        """Initialize the sensor for start or stop events."""
        self.entity_description = ENGINE_HISTORY_DESCRIPTIONS[event]
        super().__init__(coordinator, vehicle)
        self._event = event

    async def async_added_to_hass(self) -> None:
        """Restore the last recorded time and listen for new commands."""
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and isinstance(last.native_value, datetime):
            self._attr_native_value = last.native_value
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ENGINE_COMMAND.format(self._vehicle.vin),
                self._async_command_completed,
            )
        )

    @callback
    def _async_command_completed(self, event: str) -> None:
        if event == self._event:
            self._attr_native_value = dt_util.utcnow()
            self.async_write_ha_state()
