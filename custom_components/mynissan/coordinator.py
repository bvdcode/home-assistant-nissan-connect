"""Data update coordinator for MyNISSAN vehicles."""

import asyncio
import logging
from dataclasses import dataclass, field, replace
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from pynissan import (
    AuthenticationError,
    DistanceUnit,
    NissanClient,
    NissanError,
    TemperatureUnit,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
)

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NissanVehicleData:
    """Cached status and location for one vehicle."""

    status: VehicleStatus
    location: VehicleLocation
    received_at: datetime = field(default_factory=dt_util.utcnow)
    located_after_poll_failure: bool = False


type NissanCoordinatorData = dict[str, NissanVehicleData]


class NissanDataUpdateCoordinator(DataUpdateCoordinator[NissanCoordinatorData]):
    """Fetch cached status for every vehicle attached to an account."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NissanClient,
        vehicles: tuple[Vehicle, ...],
    ) -> None:
        """Initialize the account coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
            always_update=False,
        )
        self._client = client
        self._vehicles = vehicles
        match hass.config.units.length_unit:
            case UnitOfLength.KILOMETERS:
                self._distance_unit = DistanceUnit.KILOMETER
            case UnitOfLength.MILES:
                self._distance_unit = DistanceUnit.MILE
            case _:
                raise ValueError("MyNISSAN supports only kilometer and mile distance units")

        match hass.config.units.temperature_unit:
            case UnitOfTemperature.CELSIUS:
                self._temperature_unit = TemperatureUnit.CELSIUS
            case UnitOfTemperature.FAHRENHEIT:
                self._temperature_unit = TemperatureUnit.FAHRENHEIT
            case _:
                raise ValueError("MyNISSAN supports only Celsius and Fahrenheit temperature units")

    @property
    def temperature_unit(self) -> TemperatureUnit:
        """Return the Nissan temperature unit selected for Home Assistant."""
        return self._temperature_unit

    def is_location_available(self, vin: str) -> bool:
        """Return whether a poll or a completed locate supplies this vehicle's position."""
        data = self.data[vin]
        return (self.last_update_success or data.located_after_poll_failure) and _has_coordinates(
            data.location
        )

    @callback
    def async_publish_vehicle_location(
        self, previous: VehicleLocation, location: VehicleLocation | None
    ) -> bool:
        """Accept a fix newer than the starting position and keep any fresher result."""
        if (
            location is None
            or location.vin != previous.vin
            or _location_timestamp(location) is None
            or not _prefer_location(location, previous)
        ):
            return False

        vin = location.vin
        current = self.data[vin]
        best = location if _prefer_location(location, current.location) else current.location
        updated = replace(
            current, location=best, located_after_poll_failure=not self.last_update_success
        )
        if updated != current:
            self.data = {**self.data, vin: updated}
            self.async_update_listeners()
        return True

    async def _async_update_data(self) -> NissanCoordinatorData:
        """Fetch the latest cached vehicle data without waking the vehicles."""
        try:
            vehicle_data = await asyncio.gather(
                *(self._async_get_vehicle_data(vehicle) for vehicle in self._vehicles)
            )
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from error
        except NissanError as error:
            raise UpdateFailed("Unable to update MyNISSAN vehicle status") from error

        data_by_vin = {data.status.vin: data for data in vehicle_data}
        for vin, data in data_by_vin.items():
            if (
                self.data
                and (current := self.data.get(vin))
                and _prefer_location(current.location, data.location)
            ):
                data_by_vin[vin] = replace(data, location=current.location)
        return data_by_vin

    async def _async_get_vehicle_data(self, vehicle: Vehicle) -> NissanVehicleData:
        status, location = await asyncio.gather(
            self._client.async_get_vehicle_status(
                vehicle.vin,
                distance_unit=self._distance_unit,
                temperature_unit=self._temperature_unit,
            ),
            self._client.async_get_vehicle_location(vehicle.vin),
        )
        return NissanVehicleData(status, location)


def _has_coordinates(location: VehicleLocation) -> bool:
    return location.latitude is not None and location.longitude is not None


def _location_timestamp(location: VehicleLocation) -> datetime | None:
    timestamp = location.last_updated_at
    return timestamp if timestamp is not None and timestamp.utcoffset() is not None else None


def _prefer_location(candidate: VehicleLocation, other: VehicleLocation) -> bool:
    if not _has_coordinates(candidate):
        return False
    if not _has_coordinates(other):
        return True

    timestamp = _location_timestamp(candidate)
    other_timestamp = _location_timestamp(other)
    return timestamp is not None and (other_timestamp is None or timestamp > other_timestamp)
