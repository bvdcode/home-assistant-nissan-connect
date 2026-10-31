"""Estimated completion of an active charging session."""

from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from pynissan import VehicleStatus

from .entity import NissanEntity


def remaining_charge_minutes(status: VehicleStatus) -> int | None:
    """Return a valid remaining duration only while charging is active."""
    battery = status.battery
    if battery is None or battery.is_charging is not True:
        return None
    minutes = battery.remaining_charge_time
    if minutes is None or minutes < 0:
        return None
    return minutes


class NissanChargeCompletionSensor(NissanEntity, SensorEntity):
    """Estimate completion from the duration received with the cached status."""

    entity_description = SensorEntityDescription(
        key="charge_completion",
        translation_key="charge_completion",
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    @property
    def native_value(self) -> datetime | None:
        """Return the estimate anchored to the status fetch, not the current clock."""
        data = self.coordinator.data[self._vehicle.vin]
        minutes = remaining_charge_minutes(data.status)
        if minutes is None:
            return None
        return data.received_at + timedelta(minutes=minutes)
