"""The Heidelberg Energy Control integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .core.api import HeidelbergEnergyControlAPI
from .coordinator import HeidelbergEnergyControlCoordinator

_LOGGER = logging.getLogger(__name__)

type HeidelbergEnergyControlConfigEntry = ConfigEntry[
    HeidelbergEnergyControlCoordinator
]


async def async_setup_entry(
    hass: HomeAssistant, entry: HeidelbergEnergyControlConfigEntry
) -> bool:
    """Set up Heidelberg Energy Control from a config entry."""

    entry.async_on_unload(entry.add_update_listener(update_listener))

    api = HeidelbergEnergyControlAPI(
        host=entry.data["host"],
        port=entry.data["port"],
        device_id=entry.data["device_id"],
    )

    try:
        if not await api.connect():
            raise ConfigEntryNotReady(f"Unable to connect to wallbox at {api._host}")

        versions = await api.test_connection()
        if versions is None:
            await api.disconnect()
            raise ConfigEntryNotReady(
                "Wallbox connected but did not respond to version/diagnostic requests"
            )

    except Exception as err:
        if isinstance(err, ConfigEntryNotReady):
            raise
        raise ConfigEntryNotReady(f"Error communicating with wallbox: {err}") from err

    coordinator = HeidelbergEnergyControlCoordinator(
        hass=hass, api=api, versions=versions, entry=entry
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HeidelbergEnergyControlConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.api.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
