"""Exceptions for the Heidelberg Energy Control integration."""

from homeassistant.exceptions import HomeAssistantError


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the network host."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate the device is not responding (likely wrong Slave ID)."""
