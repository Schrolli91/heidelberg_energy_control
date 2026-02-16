"""Heidelberg Sensor class."""

from typing import Any

from homeassistant.components.sensor import SensorEntity

from .heidelberg_entity_base import HeidelbergEntityBase

class HeidelbergSensorCoordinator(HeidelbergEntityBase, SensorEntity):
    """Base class for coordinator data Heidelberg sensors."""

    @property
    def native_value(self) -> Any:
        """Return value from coordinator."""
        if not self.coordinator.static_data:
            return None
        return self.coordinator.static_data.get(self.entity_description.key)