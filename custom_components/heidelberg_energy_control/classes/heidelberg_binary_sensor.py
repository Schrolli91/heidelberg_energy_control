"""Binary sensor class for Heidelberg Energy Control."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from ..classes.heidelberg_entity_base import HeidelbergEntityBase


class HeidelbergBinarySensor(HeidelbergEntityBase, BinarySensorEntity):
    """Representation of a Heidelberg Binary Sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return bool(self.coordinator.data.get(self.entity_description.key, False))