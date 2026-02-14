"""HeidelbergNumber class for Heidelberg Energy Control."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity

from ..classes.heidelberg_entity_base import HeidelbergEntityBase


class HeidelbergNumber(HeidelbergEntityBase, NumberEntity):
    """Base class for Heidelberg number entities."""

    entity_description: HeidelbergNumberEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the value directly."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Write value and update coordinator data immediately."""
        modbus_value = int(value * self.entity_description.multiplier)

        await self.coordinator.api.async_write_register(
            self.entity_description.register, modbus_value
        )

        # Optimistic update
        self.coordinator.data[self.entity_description.key] = value
        self.coordinator.async_set_updated_data(self.coordinator.data)