"""HeidelbergNumber class for Heidelberg Energy Control."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity

from ..classes.heidelberg_entity_base import HeidelbergEntityBase


class HeidelbergNumber(HeidelbergEntityBase, NumberEntity):
    """Base class for Heidelberg hardware number entities (Modbus).

    Coordinator data holds raw wire values (e.g. deci-amps, milliseconds).
    The entity's `multiplier` converts between display units and the wire
    format symmetrically: divide on read, multiply on write. A `None`
    multiplier means the wire value is already the display value on both
    sides.
    """

    @property
    def native_value(self) -> float | None:
        """Return the display value, converted from the raw coordinator data."""
        raw = self.coordinator.data.get(self.entity_description.key)
        if raw is None:
            return None
        if self.entity_description.multiplier is None:
            return raw
        return raw / self.entity_description.multiplier

    async def async_set_native_value(self, value: float) -> None:
        """Write value to hardware and update coordinator data."""
        if self.entity_description.multiplier is None:
            modbus_value = int(value)
        else:
            modbus_value = int(value * self.entity_description.multiplier)

        success = await self.coordinator.api.async_write_command(
            self.entity_description.key, modbus_value
        )

        if success:
            self.coordinator.data[self.entity_description.key] = modbus_value
            self.coordinator.async_set_updated_data(self.coordinator.data)
