"""Heidelberg Sensor Active Phases class."""

from typing import Any

from homeassistant.components.sensor import SensorEntity

from .heidelberg_sensor import HeidelbergSensor


class HeidelbergSensorActivePhases(HeidelbergSensor, SensorEntity):
    """Class for the active phases sensor with dynamic icon."""

    @property
    def icon(self) -> str | None:
        """Dynamically return the icon based on the state."""
        return f"mdi:numeric-{int(self.native_value or 0)}-box-outline"
