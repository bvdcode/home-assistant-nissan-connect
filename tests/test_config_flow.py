"""Tests for the MyNISSAN config flow."""

from unittest.mock import MagicMock

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pynissan import AuthenticationError, Country, NetworkError, NissanError, Tokens, Vehicle
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mynissan.const import (
    CONF_AUTH_PROFILE,
    CONF_COUNTRY,
    CONF_OAUTH_DEVICE_ID,
    CONF_TOKENS,
    DOMAIN,
    MOBILE_AUTH_PROFILE,
)

EMAIL = "driver@example.com"
PASSWORD = "secret"
TOKENS = Tokens("access", "refresh", "id")
VEHICLE = Vehicle("JN1TESTVIN0000001", "2025", "ARIYA", None, "Ariya", None, None, None)


async def test_user_flow_creates_entry(
    hass: HomeAssistant,
    mock_nissan_client: MagicMock,
) -> None:
    """A valid account creates one token-backed config entry."""
    mock_nissan_client.async_authenticate.return_value = TOKENS
    mock_nissan_client.async_get_vehicles.return_value = (VEHICLE,)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: Country.US.value.lower(),
            CONF_EMAIL: " Driver@Example.com ",
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"] == {
        CONF_AUTH_PROFILE: MOBILE_AUTH_PROFILE,
        CONF_COUNTRY: "US",
        CONF_EMAIL: EMAIL,
        CONF_OAUTH_DEVICE_ID: "oauth-device-id",
        CONF_TOKENS: {
            "access_token": "access",
            "refresh_token": "refresh",
            "id_token": "id",
        },
    }
    assert CONF_PASSWORD not in result["data"]
    assert result["result"].unique_id == f"US:{EMAIL}"


@pytest.mark.parametrize("country", (Country.CA, Country.MX))
async def test_user_flow_supports_account_country(
    hass: HomeAssistant,
    mock_nissan_client: MagicMock,
    country: Country,
) -> None:
    """The selected account country is stored in the config entry identity."""
    mock_nissan_client.async_authenticate.return_value = TOKENS
    mock_nissan_client.async_get_vehicles.return_value = (VEHICLE,)

    result = await _submit_user_flow(hass, country=country)

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_COUNTRY] == country.value
    assert result["result"].unique_id == f"{country.value}:{EMAIL}"


async def test_user_flow_rejects_invalid_authentication(
    hass: HomeAssistant,
    mock_nissan_client: MagicMock,
) -> None:
    """Invalid credentials remain on the form with a useful error."""
    mock_nissan_client.async_authenticate.side_effect = AuthenticationError(
        401,
        "Unauthorized",
    )

    result = await _submit_user_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_handles_network_failure(
    hass: HomeAssistant,
    mock_nissan_client: MagicMock,
) -> None:
    """Network failures remain on the form with a retryable error."""
    mock_nissan_client.async_authenticate.side_effect = NetworkError

    result = await _submit_user_flow(hass)

    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_handles_unexpected_api_failure(
    hass: HomeAssistant,
    mock_nissan_client: MagicMock,
) -> None:
    """Unexpected SDK failures are mapped to the generic form error."""
    mock_nissan_client.async_authenticate.side_effect = NissanError

    result = await _submit_user_flow(hass)

    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_requires_a_vehicle(
    hass: HomeAssistant,
    mock_nissan_client: MagicMock,
) -> None:
    """Accounts without vehicles are rejected explicitly."""
    mock_nissan_client.async_authenticate.return_value = TOKENS
    mock_nissan_client.async_get_vehicles.return_value = ()

    result = await _submit_user_flow(hass)

    assert result["errors"] == {"base": "no_vehicles"}


async def test_user_flow_aborts_duplicate_account(
    hass: HomeAssistant,
) -> None:
    """An account can only be configured once."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"US:{EMAIL}",
        data={CONF_COUNTRY: "US", CONF_EMAIL: EMAIL},
    ).add_to_hass(hass)

    result = await _submit_user_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauthentication_updates_tokens(
    hass: HomeAssistant,
    mock_nissan_client: MagicMock,
) -> None:
    """Reauthentication replaces tokens without storing the password."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"US:{EMAIL}",
        data=_entry_data(),
    )
    entry.add_to_hass(hass)
    mock_nissan_client.async_authenticate.return_value = TOKENS
    mock_nissan_client.async_get_vehicles.return_value = (VEHICLE,)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: PASSWORD},
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKENS] == {
        "access_token": "access",
        "refresh_token": "refresh",
        "id_token": "id",
    }
    assert entry.data[CONF_AUTH_PROFILE] == MOBILE_AUTH_PROFILE
    assert CONF_PASSWORD not in entry.data


async def _submit_user_flow(
    hass: HomeAssistant,
    *,
    country: Country = Country.US,
) -> config_entries.ConfigFlowResult:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: country.value.lower(),
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: PASSWORD,
        },
    )


def _entry_data() -> dict[str, object]:
    return {
        CONF_AUTH_PROFILE: MOBILE_AUTH_PROFILE,
        CONF_COUNTRY: "US",
        CONF_EMAIL: EMAIL,
        CONF_OAUTH_DEVICE_ID: "old-device-id",
        CONF_TOKENS: {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "id_token": "old-id",
        },
    }
