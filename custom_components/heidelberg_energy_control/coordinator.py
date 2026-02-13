"""Coordinator for Heidelberg Energy Control integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COMMAND_MAX_CURRENT, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HeidelbergEnergyControlCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching from the wallbox."""

    def __init__(self, hass: HomeAssistant, api: Any, versions: dict[str, str]) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.versions = versions

        # Proxy storage for EVCC and UI
        # We use float (actual Amperes) as the API provides them this way
        self.target_current: float = 16.0  # Default 16A
        self.logic_enabled: bool = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the wallbox via the single-call API method."""
        _LOGGER.debug("Fetching data from Heidelberg Energy Control")

        data = await self.api.async_get_data()

        if data:
            # The API already provides the value divided by 10 (e.g., 11.5)
            # We ensure it is a float
            hw_current = data.get(COMMAND_MAX_CURRENT, 0.0)

            if hw_current > 0:
                self.target_current = float(hw_current)
                self.logic_enabled = True

            # If hw_current == 0, logic_enabled remains False
            # (or at the value set by the switch's restore state).

        return data