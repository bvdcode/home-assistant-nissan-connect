"""Data update coordinator for MyNISSAN vehicles."""

import asyncio
import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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

        return {data.status.vin: data for data in vehicle_data}

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
