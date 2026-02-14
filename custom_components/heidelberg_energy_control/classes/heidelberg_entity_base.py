"""Heidelberg Entity Base class."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .. import HeidelbergEnergyControlConfigEntry
from ..const import DEVICE_MANUFACTURER, DEVICE_MODEL, DOMAIN
from ..coordinator import HeidelbergEnergyControlCoordinator


class HeidelbergEntityBase(CoordinatorEntity[HeidelbergEnergyControlCoordinator]):
    """Common base for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeidelbergEnergyControlCoordinator,
        entry: HeidelbergEnergyControlConfigEntry,
        description: Any,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            hw_version=self.coordinator.versions.get("hw_version"),
            sw_version=self.coordinator.versions.get("sw_version"),
        )
