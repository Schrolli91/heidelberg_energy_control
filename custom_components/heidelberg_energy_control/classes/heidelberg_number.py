"""HeidelbergNumber class for Heidelberg Energy Control."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity

from ..classes.heidelberg_entity_base import HeidelbergEntityBase

_LOGGER = logging.getLogger(__name__)


class HeidelbergNumber(HeidelbergEntityBase, NumberEntity):
    """Base class for Heidelberg hardware number entities (Modbus)."""

    @property
    def native_value(self) -> float | None:
        """Return the value from coordinator data."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Write value to hardware and update coordinator data."""

        if self.entity_description.multiplier is None:
            _LOGGER.error(
                "Cannot write %s: Missing multiplier in description",
                self.entity_description.key,
            )
            return

        modbus_value = int(value * self.entity_description.multiplier)

        success = await self.coordinator.api.async_write_command(
            self.entity_description.key, modbus_value
        )

        if success:
            self.coordinator.data[self.entity_description.key] = value
            self.coordinator.async_set_updated_data(self.coordinator.data)
