"""Configuration flow for MyNISSAN."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TypedDict, cast

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import selector
from pynissan import AuthenticationError, NetworkError, NissanError

from .api import ValidatedAccount, async_validate_credentials, tokens_to_data
from .const import (
    CONF_COUNTRY,
    CONF_OAUTH_DEVICE_ID,
    DEFAULT_COUNTRY,
    DOMAIN,
)
from .models import NissanConfigData

_LOGGER = logging.getLogger(__name__)


class CredentialsInput(TypedDict):
    """Credentials submitted through a config flow form."""

    email: str
    password: str


class PasswordInput(TypedDict):
    """Password submitted through a reauthentication form."""

    password: str


EMAIL_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(
        type=selector.TextSelectorType.EMAIL,
        autocomplete="email",
    )
)
PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(
        type=selector.TextSelectorType.PASSWORD,
        autocomplete="current-password",
    )
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): EMAIL_SELECTOR,
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR})


class MyNissanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Manage MyNISSAN configuration entries."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, object] | None = None,
    ) -> ConfigFlowResult:
        """Create a config entry from MyNISSAN account credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            credentials = cast(CredentialsInput, user_input)
            email = credentials[CONF_EMAIL].strip().casefold()
            self._async_abort_entries_match(
                {
                    CONF_COUNTRY: DEFAULT_COUNTRY.value,
                    CONF_EMAIL: email,
                }
            )

            account, error = await self._async_validate_account(
                email=email,
                password=credentials[CONF_PASSWORD],
            )
            if account is not None:
                await self.async_set_unique_id(
                    f"{DEFAULT_COUNTRY.value}:{email}",
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data=NissanConfigData(
                        country=DEFAULT_COUNTRY.value,
                        email=email,
                        oauth_device_id=account.oauth_device_id,
                        tokens=tokens_to_data(account.tokens),
                    ),
                )
            if error is not None:
                errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, object],
    ) -> ConfigFlowResult:
        """Start reauthentication for an existing config entry."""
        del entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, object] | None = None,
    ) -> ConfigFlowResult:
        """Validate a new password and update stored OAuth tokens."""
        entry = self.hass.config_entries.async_get_known_entry(
            self.context["entry_id"],
        )
        data = cast(NissanConfigData, entry.data)
        errors: dict[str, str] = {}

        if user_input is not None:
            password_input = cast(PasswordInput, user_input)
            account, error = await self._async_validate_account(
                email=data[CONF_EMAIL],
                password=password_input[CONF_PASSWORD],
                oauth_device_id=data[CONF_OAUTH_DEVICE_ID],
            )
            if account is not None:
                updated_data = NissanConfigData(
                    country=data[CONF_COUNTRY],
                    email=data[CONF_EMAIL],
                    oauth_device_id=account.oauth_device_id,
                    tokens=tokens_to_data(account.tokens),
                )
                return self.async_update_reload_and_abort(
                    entry,
                    data=updated_data,
                )
            if error is not None:
                errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"email": data[CONF_EMAIL]},
        )

    async def _async_validate_account(
        self,
        *,
        email: str,
        password: str,
        oauth_device_id: str | None = None,
    ) -> tuple[ValidatedAccount | None, str | None]:
        """Validate credentials and translate client failures for the form."""
        try:
            account = await async_validate_credentials(
                self.hass,
                email=email,
                password=password,
                country=DEFAULT_COUNTRY,
                oauth_device_id=oauth_device_id,
            )
        except AuthenticationError:
            return None, "invalid_auth"
        except NetworkError:
            return None, "cannot_connect"
        except NissanError:
            _LOGGER.exception("Unexpected MyNISSAN API error during authentication")
            return None, "unknown"

        if not account.vehicles:
            return None, "no_vehicles"
        return account, None
