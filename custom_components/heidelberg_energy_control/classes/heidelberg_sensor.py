"""Heidelberg Sensor class."""

from typing import Any

from homeassistant.components.sensor import SensorEntity

from .heidelberg_entity_base import HeidelbergEntityBase

class HeidelbergSensor(HeidelbergEntityBase, SensorEntity):
    """Base class for standard Heidelberg sensors."""

    @property
    def native_value(self) -> Any:
        """Return value from coordinator."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)