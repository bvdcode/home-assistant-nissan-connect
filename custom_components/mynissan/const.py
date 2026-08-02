"""Constants for the MyNISSAN integration."""

from datetime import timedelta
from typing import Final

from pynissan import Country

DOMAIN: Final = "mynissan"
MANUFACTURER: Final = "Nissan"

CONF_ACCESS_TOKEN: Final = "access_token"
CONF_COUNTRY: Final = "country"
CONF_ID_TOKEN: Final = "id_token"
CONF_OAUTH_DEVICE_ID: Final = "oauth_device_id"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_TOKENS: Final = "tokens"

DEFAULT_COUNTRY: Final = Country.US
DEFAULT_UPDATE_INTERVAL: Final = timedelta(minutes=15)
