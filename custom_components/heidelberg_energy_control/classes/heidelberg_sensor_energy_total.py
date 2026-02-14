"""Heidelberg Sensor Energy Total class."""

import logging

from .heidelberg_sensor_energy_base import HeidelbergSensorEnergyBase

_LOGGER = logging.getLogger(__name__)


class HeidelbergSensorEnergyTotal(HeidelbergSensorEnergyBase):
    """Total energy sensor that corrects hardware counter resets."""

    @property
    def native_value(self) -> float | None:
        """Return corrected total energy."""
        raw_total = self.coordinator.data.get(self.entity_description.key)
        if raw_total is None:
            return self._attr_native_value

        # This updates the offset and stores the current raw_total as last_raw_value
        self._attr_native_value = round(self._get_corrected_total(raw_total), 2)
        return self._attr_native_value
