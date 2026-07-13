"""Switch entity for Heidelberg Energy Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity

from ..classes.heidelberg_entity_base import HeidelbergEntityBase


class HeidelbergSwitch(HeidelbergEntityBase, SwitchEntity):
    """Generic representation of a logic switch."""

    @property
    def is_on(self) -> bool:
        """Return the state from the central coordinator data store."""
        return self.coordinator.data.get(self.entity_description.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on request to coordinator."""
        success = await self.coordinator.api.async_write_command(
            self.entity_description.key, self.entity_description.on_value
        )

        if success:
            self.coordinator.data[self.entity_description.key] = 1
            self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off request to coordinator."""
        success = await self.coordinator.api.async_write_command(
            self.entity_description.key, self.entity_description.off_value
        )

        if success:
            self.coordinator.data[self.entity_description.key] = 0
            self.coordinator.async_set_updated_data(self.coordinator.data)
