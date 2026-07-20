"""Heidelberg Sensor class."""

from typing import Any

from homeassistant.components.sensor import SensorEntity

from .heidelberg_entity_base import HeidelbergEntityBase

class HeidelbergSensor(HeidelbergEntityBase, SensorEntity):
    """Base class for standard Heidelberg sensors."""

    @property
    def native_value(self) -> Any:
        """Return the display value from coordinator data.

        If the description carries a `multiplier`, the sensor mirrors the
        number-entity contract: capability data is raw wire form, sensor
        divides on read.
        """
        if not self.coordinator.data:
            return None
        raw = self.coordinator.data.get(self.entity_description.key)
        if raw is None:
            return None
        multiplier = getattr(self.entity_description, "multiplier", None)
        if multiplier is None:
            return raw
        return raw / multiplier