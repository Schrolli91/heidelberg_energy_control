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

        # Guard clause: Ensure register and multiplier are present
        if (
            self.entity_description.register is None
            or self.entity_description.multiplier is None
        ):
            _LOGGER.error(
                "Cannot write %s: Missing register or multiplier in description",
                self.entity_description.key,
            )
            return

        # Calculate the raw value for Modbus
        modbus_value = int(value * self.entity_description.multiplier)

        # Write to the physical register via API
        success = await self.coordinator.api.async_write_register(
            self.entity_description.register, modbus_value
        )

        if success:
            # Optimistic update of the coordinator data
            self.coordinator.data[self.entity_description.key] = value
            self.coordinator.async_set_updated_data(self.coordinator.data)
