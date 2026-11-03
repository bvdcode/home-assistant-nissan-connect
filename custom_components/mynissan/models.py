"""Data models for the MyNISSAN integration."""

from dataclasses import dataclass, field
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from pynissan import NissanClient, Vehicle, VehicleCapabilities

from .coordinator import NissanDataUpdateCoordinator
from .engine_climate import EngineClimate


class StoredTokens(TypedDict):
    """Serializable OAuth token data stored by Home Assistant."""

    access_token: str
    refresh_token: str
    id_token: str | None


class NissanConfigData(TypedDict):
    """Serializable MyNISSAN config entry data."""

    auth_profile: str
    country: str
    email: str
    oauth_device_id: str
    tokens: StoredTokens


@dataclass(frozen=True, slots=True)
class NissanRuntimeData:
    """Runtime objects owned by a loaded config entry."""

    client: NissanClient
    vehicles: tuple[Vehicle, ...]
    capabilities: dict[str, VehicleCapabilities]
    coordinator: NissanDataUpdateCoordinator
    engine_climate: dict[str, EngineClimate] = field(default_factory=dict)


type NissanConfigEntry = ConfigEntry[NissanRuntimeData]
