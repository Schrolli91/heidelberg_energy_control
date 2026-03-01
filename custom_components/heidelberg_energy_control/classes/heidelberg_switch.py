"""Switch entity for Heidelberg Energy Control."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity

from ..classes.heidelberg_entity_base import HeidelbergEntityBase

_LOGGER = logging.getLogger(__name__)


class HeidelbergSwitch(HeidelbergEntityBase, SwitchEntity):
    """Generic representation of a logic switch."""

    @property
    def is_on(self) -> bool:
        """Return the state from the central coordinator data store."""
        return self.coordinator.data.get(self.entity_description.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on request to coordinator."""
        if not self._guard():
            return

        # Write to the physical register via API
        success = await self.coordinator.api.async_write_register(
            self.entity_description.register, self.entity_description.on_value
        )

        if success:
            # Optimistic update of the coordinator data
            self.coordinator.data[self.entity_description.key] = 1
            self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off request to coordinator."""
        if not self._guard():
            return

        # Write to the physical register via API
        success = await self.coordinator.api.async_write_register(
            self.entity_description.register, self.entity_description.off_value
        )

        if success:
            # Optimistic update of the coordinator data
            self.coordinator.data[self.entity_description.key] = 0
            self.coordinator.async_set_updated_data(self.coordinator.data)

    def _guard(self) -> bool:
        # Guard clause: Ensure register are present
        if self.entity_description.register is None:
            _LOGGER.error(
                "Cannot write %s: Missing register in description",
                self.entity_description.key,
            )
            return False
        return True
