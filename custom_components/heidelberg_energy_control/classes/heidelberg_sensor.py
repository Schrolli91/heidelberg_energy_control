"""Heidelberg Sensor class."""

from typing import Any

from homeassistant.components.sensor import SensorEntity

from .heidelberg_entity_base import HeidelbergEntityBase

class HeidelbergSensor(HeidelbergEntityBase, SensorEntity):
    """Base class for standard Heidelberg sensors.

    Coordinator data holds raw wire values (e.g. deci-amps, milliseconds).
    The entity's `multiplier` converts to display units on read. A `None`
    multiplier means the wire value is already the display value.
    """

    @property
    def native_value(self) -> Any:
        """Return the display value, converted from the raw coordinator data."""
        if not self.coordinator.data:
            return None
        raw = self.coordinator.data.get(self.entity_description.key)
        if raw is None:
            return None
        if self.entity_description.multiplier is None:
            return raw
        return raw / self.entity_description.multiplier