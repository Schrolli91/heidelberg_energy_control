"""Virtual number entity for Heidelberg Energy Control."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.restore_state import RestoreEntity

from ..classes.heidelberg_entity_base import HeidelbergEntityBase


class HeidelbergNumberVirtual(HeidelbergEntityBase, NumberEntity, RestoreEntity):
    """Generic representation of a number entity using proxy logic."""

    async def async_added_to_hass(self) -> None:
        """Restore state and sync value with coordinator."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            if state.state not in ("unknown", "unavailable"):
                # Pass the restored value to the coordinator dispatcher
                await self.coordinator.async_handle_number_set(
                    self.entity_description.key, float(state.state)
                )

    @property
    def native_value(self) -> float | None:
        """Return value from coordinator storage using the entity key."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Forward slider change to coordinator dispatcher."""
        await self.coordinator.async_handle_number_set(
            self.entity_description.key, value
        )