"""Heidelberg Sensor class."""

from typing import Any

from homeassistant.components.sensor import SensorEntity

from .heidelberg_entity_base import HeidelbergEntityBase
from ..const import DATA_PHASES_ACTIVE


class HeidelbergSensor(HeidelbergEntityBase, SensorEntity):
    """Base class for standard Heidelberg sensors."""

    @property
    def icon(self) -> str | None:
        """Dynamically return the icon based on the state."""
        if self.entity_description.key == DATA_PHASES_ACTIVE:
            return f"mdi:numeric-{int(self.native_value or 0)}-box-outline"

        return self.entity_description.icon

    @property
    def native_value(self) -> Any:
        """Return value from coordinator."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)