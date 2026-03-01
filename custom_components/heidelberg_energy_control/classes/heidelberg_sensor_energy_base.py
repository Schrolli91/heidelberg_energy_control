"""Heidelberg Sensor Energy Base class."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .heidelberg_entity_base import HeidelbergEntityBase

_LOGGER = logging.getLogger(__name__)


class HeidelbergSensorEnergyBase(HeidelbergEntityBase, RestoreEntity, SensorEntity):
    """Base for energy sensors with jump protection and state restoration."""

    def __init__(self, coordinator, entry, description):
        """Initialize energy base sensor."""
        super().__init__(coordinator, entry, description)
        self._total_offset: float = 0.0
        self._last_raw_value: float | None = None
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore internal tracking values on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            offset_val = last_state.attributes.get("_total_offset")
            self._total_offset = float(offset_val) if offset_val is not None else 0.0

            raw_val = last_state.attributes.get("_last_raw_value")
            self._last_raw_value = float(raw_val) if raw_val is not None else None

            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError) as _:
                self._attr_native_value = 0.0

    def _get_corrected_total(self, raw_total: float) -> float:
        """Handle hardware jumps by maintaining a virtual offset."""
        if self._last_raw_value is not None and raw_total < self._last_raw_value:
            jump = self._last_raw_value - raw_total
            self._total_offset += jump
            _LOGGER.warning(
                "Counter jump detected for %s: +%s kWh offset applied",
                self.entity_id,
                jump,
            )

        self._last_raw_value = raw_total
        return raw_total + self._total_offset

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return internal values as hidden attributes for restoration."""
        return {
            "_total_offset": self._total_offset,
            "_last_raw_value": self._last_raw_value,
        }
