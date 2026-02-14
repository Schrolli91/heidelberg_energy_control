"""Heidelberg Sensor Energy Session class."""

from typing import Any

from .heidelberg_sensor_energy_base import HeidelbergSensorEnergyBase
from ..const import DATA_TOTAL_ENERGY, DATA_IS_PLUGGED


class HeidelbergSensorEnergySession(HeidelbergSensorEnergyBase):
    """Session energy sensor with jump protection and 'reset-on-connect' logic."""

    def __init__(self, coordinator, entry, description):
        """Initialize session sensor."""
        super().__init__(coordinator, entry, description)
        self._start_corrected_value: float | None = None
        self._last_is_plugged: bool = False

    async def async_added_to_hass(self) -> None:
        """Restore session start reference point."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            # Load stored attributes
            self._start_corrected_value = last_state.attributes.get("_start_corrected")
            # Ensure last_is_plugged is a clean boolean
            last_plugged_attr = last_state.attributes.get("_last_is_plugged", False)
            self._last_is_plugged = str(last_plugged_attr).lower() == "true"

    @property
    def native_value(self) -> float | None:
        """Calculate session energy with auto-initialization."""
        data = self.coordinator.data
        if not data:
            return self._attr_native_value

        raw_total = data.get(DATA_TOTAL_ENERGY)
        # Force conversion to bool to avoid type mismatches
        is_plugged = bool(data.get(DATA_IS_PLUGGED, False))

        if raw_total is None:
            return self._attr_native_value

        # 1. Update correction logic from base class
        current_corrected = self._get_corrected_total(raw_total)

        # 2. Reset / Start detection logic
        if is_plugged:
            # Condition 1: Car was just plugged in (Edge Detection)
            # Condition 2: Car is plugged in but we have no start value (First run/Recovery)
            if not self._last_is_plugged or self._start_corrected_value is None:
                # If we were already plugged but lost the start value,
                # we initialize it now to allow counting to start.
                if self._start_corrected_value is None or not self._last_is_plugged:
                    self._start_corrected_value = current_corrected
                    # Only reset the display value if it's a truly NEW session
                    if not self._last_is_plugged:
                        self._attr_native_value = 0.0
                    _LOGGER.debug(
                        "Session initialized/reset at %s kWh (is_plugged: %s)",
                        current_corrected,
                        is_plugged,
                    )

            # 3. Active Calculation
            # This will now always run as soon as is_plugged is true and a start value exists
            if self._start_corrected_value is not None:
                self._attr_native_value = max(
                    0.0, round(current_corrected - self._start_corrected_value, 2)
                )

        # Update tracking variable for next poll
        self._last_is_plugged = is_plugged
        return self._attr_native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Add session-specific internal attributes."""
        attrs = super().extra_state_attributes
        attrs.update(
            {
                "_start_corrected": self._start_corrected_value,
                "_last_is_plugged": self._last_is_plugged,
            }
        )
        return attrs