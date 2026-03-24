"""Exceptions for the Heidelberg Energy Control integration."""

from homeassistant.exceptions import HomeAssistantError


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the network host."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate the device is not responding (likely wrong Slave ID)."""


class HeidelbergEnergyControlAPIError(HomeAssistantError):
    """Base exception for Heidelberg Energy Control API errors."""


class HeidelbergEnergyControlConnectionError(HeidelbergEnergyControlAPIError):
    """Error to indicate a connection problem with the wallbox."""


class HeidelbergEnergyControlReadError(HeidelbergEnergyControlAPIError):
    """Error to indicate a read error from the wallbox."""


class HeidelbergEnergyControlWriteError(HeidelbergEnergyControlAPIError):
    """Error to indicate a write error to the wallbox."""
