"""Hardware-backed session energy sensor (v2.0.0+)."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .heidelberg_entity_base import HeidelbergEntityBase

_LOGGER = logging.getLogger(__name__)


class HeidelbergSensorEnergyHwSession(HeidelbergEntityBase, RestoreEntity, SensorEntity):
    """Session energy read from hardware register 19..20.

    The wallbox itself resets the register when the vehicle disconnects,
    so downward moves are expected and passed through as-is. That's the
    reason this class doesn't inherit HeidelbergSensorEnergyBase's
    jump-correction: applying an offset to a legitimate reset would
    freeze the sensor at the pre-reset high-water mark forever.
    """

    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator, entry, description)
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError):
                self._attr_native_value = None

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.get(self.entity_description.key)
        if raw is None:
            return self._attr_native_value
        self._attr_native_value = round(raw, 2)
        return self._attr_native_value
