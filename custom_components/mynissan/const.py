"""Constants for the MyNISSAN integration."""

from datetime import timedelta
from typing import Final

from pynissan import Country

DOMAIN: Final = "mynissan"
MANUFACTURER: Final = "Nissan"

CONF_ACCESS_TOKEN: Final = "access_token"
CONF_AUTH_PROFILE: Final = "auth_profile"
CONF_COUNTRY: Final = "country"
CONF_ID_TOKEN: Final = "id_token"
CONF_OAUTH_DEVICE_ID: Final = "oauth_device_id"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_TOKENS: Final = "tokens"

DEFAULT_COUNTRY: Final = Country.US
DEFAULT_UPDATE_INTERVAL: Final = timedelta(minutes=15)
MOBILE_AUTH_PROFILE: Final = "mobile"
REMOTE_CLIMATE_CONTROL_SERVICE: Final = "REMOTE_CLIMATE_CONTROL"

# Sent with the vehicle VIN when a remote engine command completes successfully.
SIGNAL_ENGINE_COMMAND: Final = "mynissan_engine_command_{}"
ENGINE_START_EVENT: Final = "start"
ENGINE_STOP_EVENT: Final = "stop"
SERVICE_REMOTE_ENGINE_START: Final = "remote_engine_start"


def country_from_value(value: str) -> Country:
    """Return the SDK country matching stored config entry data."""
    match value:
        case Country.US.value:
            return Country.US
        case Country.CA.value:
            return Country.CA
        case Country.MX.value:
            return Country.MX
        case _:
            raise ValueError(f"Unsupported country: {value}")
