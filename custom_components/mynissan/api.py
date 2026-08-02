"""MyNISSAN client construction and account validation."""

from collections.abc import Mapping
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pynissan import Country, NissanClient, TokenListener, Tokens, Vehicle

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_REFRESH_TOKEN,
)
from .models import StoredTokens


@dataclass(frozen=True, slots=True)
class ValidatedAccount:
    """Authenticated account data returned to the config flow."""

    tokens: Tokens
    oauth_device_id: str
    vehicles: tuple[Vehicle, ...]


def tokens_to_data(tokens: Tokens) -> StoredTokens:
    """Convert OAuth tokens to serializable config entry data."""
    return StoredTokens(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        id_token=tokens.id_token,
    )


def tokens_from_data(data: Mapping[str, object]) -> Tokens:
    """Create OAuth tokens from config entry data."""
    access_token = data.get(CONF_ACCESS_TOKEN)
    refresh_token = data.get(CONF_REFRESH_TOKEN)
    id_token = data.get(CONF_ID_TOKEN)

    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        raise ValueError("Stored OAuth tokens are invalid")
    if id_token is not None and not isinstance(id_token, str):
        raise ValueError("Stored ID token is invalid")

    return Tokens(
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=id_token,
    )


def create_client(
    hass: HomeAssistant,
    *,
    country: Country,
    tokens: Tokens,
    oauth_device_id: str,
    token_listener: TokenListener,
) -> NissanClient:
    """Create a read-only client using Home Assistant's HTTP session."""
    return NissanClient(
        async_get_clientsession(hass),
        country=country,
        tokens=tokens,
        token_listener=token_listener,
        read_only=True,
        oauth_device_id=oauth_device_id,
    )


async def async_validate_credentials(
    hass: HomeAssistant,
    *,
    email: str,
    password: str,
    country: Country,
    oauth_device_id: str | None = None,
) -> ValidatedAccount:
    """Authenticate credentials and discover the account's vehicles."""
    client = NissanClient(
        async_get_clientsession(hass),
        country=country,
        read_only=True,
        oauth_device_id=oauth_device_id,
    )
    tokens = await client.async_authenticate(email, password)
    vehicles = await client.async_get_vehicles()
    return ValidatedAccount(
        tokens=tokens,
        oauth_device_id=client.oauth_device_id,
        vehicles=vehicles,
    )
