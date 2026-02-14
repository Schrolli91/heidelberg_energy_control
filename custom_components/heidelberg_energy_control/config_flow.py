"""Config flow for the Heidelberg Energy Control integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .core.exceptions import CannotConnect, InvalidAuth

from .api import HeidelbergEnergyControlAPI
from .const import CONF_DEVICE_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Wallbox"): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=502): int,
        vol.Required(CONF_DEVICE_ID, default=1): int,
    }
)


async def validate_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = HeidelbergEnergyControlAPI(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        device_id=data[CONF_DEVICE_ID],
    )

    try:
        if not await api.connect():
            raise CannotConnect

        versions = await api.test_connection()
        await api.disconnect()

        if versions is None:
            raise InvalidAuth

    except (CannotConnect, InvalidAuth):
        raise
    except Exception as err:
        _LOGGER.error("Connection validation failed: %s", err)
        raise CannotConnect from err

    return {"title": data[CONF_NAME]}


class HeidelbergEnergyControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Heidelberg Energy Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HeidelbergOptionsFlowHandler:
        """Get the options flow for this handler."""
        return HeidelbergOptionsFlowHandler()


class HeidelbergOptionsFlowHandler(OptionsFlow):
    """Handle the options flow for the integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=3,
                            max=30,
                            step=1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,  # BOX macht ein sauberes Eingabefeld statt Schieberegler
                        ),
                    ),
                }
            ),
        )
