"""MyNISSAN integration for Home Assistant."""

import asyncio
from collections.abc import Mapping
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from pynissan import AuthenticationError, NetworkError, NissanError, Tokens, Vehicle

from .api import create_client, tokens_from_data, tokens_to_data
from .const import (
    CONF_AUTH_PROFILE,
    CONF_COUNTRY,
    CONF_OAUTH_DEVICE_ID,
    CONF_TOKENS,
    DOMAIN,
    MANUFACTURER,
    MOBILE_AUTH_PROFILE,
    country_from_value,
)
from .coordinator import NissanDataUpdateCoordinator
from .models import NissanConfigData, NissanConfigEntry, NissanRuntimeData

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
)


async def async_setup_entry(hass: HomeAssistant, entry: NissanConfigEntry) -> bool:
    """Set up a MyNISSAN account from a config entry."""
    data = cast(NissanConfigData, entry.data)
    if data.get(CONF_AUTH_PROFILE) != MOBILE_AUTH_PROFILE:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        )

    @callback
    def async_store_tokens(tokens: Tokens) -> None:
        """Persist refreshed OAuth tokens in the config entry."""
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_TOKENS: tokens_to_data(tokens)},
        )

    try:
        country = country_from_value(data[CONF_COUNTRY])
        tokens_data = cast(Mapping[str, object], data[CONF_TOKENS])
        client = create_client(
            hass,
            country=country,
            tokens=tokens_from_data(tokens_data),
            oauth_device_id=data[CONF_OAUTH_DEVICE_ID],
            token_listener=async_store_tokens,
        )
        vehicles = await client.async_get_vehicles()
    except AuthenticationError as error:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from error
    except NetworkError as error:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from error
    except (NissanError, ValueError) as error:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="api_error",
        ) from error

    if not vehicles:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_vehicles",
        )

    coordinator = NissanDataUpdateCoordinator(hass, entry, client, vehicles)
    try:
        vehicle_capabilities = await asyncio.gather(
            *(
                client.async_get_vehicle_capabilities(
                    vehicle.vin,
                    coordinator.temperature_unit,
                )
                for vehicle in vehicles
            )
        )
    except AuthenticationError as error:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from error
    except NetworkError as error:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from error
    except NissanError as error:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="api_error",
        ) from error

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = NissanRuntimeData(
        client=client,
        vehicles=vehicles,
        capabilities={capabilities.vin: capabilities for capabilities in vehicle_capabilities},
        coordinator=coordinator,
    )
    _register_vehicles(hass, entry, vehicles)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a MyNISSAN config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def _register_vehicles(
    hass: HomeAssistant,
    entry: NissanConfigEntry,
    vehicles: tuple[Vehicle, ...],
) -> None:
    """Register every discovered vehicle as a Home Assistant device."""
    registry = dr.async_get(hass)
    for vehicle in vehicles:
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, vehicle.vin)},
            manufacturer=MANUFACTURER,
            model=vehicle.model,
            name=_vehicle_name(vehicle),
            serial_number=vehicle.vin,
        )


def _vehicle_name(vehicle: Vehicle) -> str:
    """Build a useful device name from known vehicle data."""
    if vehicle.nickname:
        return vehicle.nickname

    year_and_model = " ".join(part for part in (vehicle.year, vehicle.model) if part is not None)
    if year_and_model:
        return year_and_model
    return f"Nissan {vehicle.vin[-4:]}"
