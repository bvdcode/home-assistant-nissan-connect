"""Data models for the MyNISSAN integration."""

from dataclasses import dataclass
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from pynissan import NissanClient, Vehicle

from .coordinator import NissanDataUpdateCoordinator


class StoredTokens(TypedDict):
    """Serializable OAuth token data stored by Home Assistant."""

    access_token: str
    refresh_token: str
    id_token: str | None


class NissanConfigData(TypedDict):
    """Serializable MyNISSAN config entry data."""

    country: str
    email: str
    oauth_device_id: str
    tokens: StoredTokens


@dataclass(frozen=True, slots=True)
class NissanRuntimeData:
    """Runtime objects owned by a loaded config entry."""

    client: NissanClient
    vehicles: tuple[Vehicle, ...]
    coordinator: NissanDataUpdateCoordinator


type NissanConfigEntry = ConfigEntry[NissanRuntimeData]
