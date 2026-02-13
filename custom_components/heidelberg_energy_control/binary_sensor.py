"""Binary sensor platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .const import DATA_EXTERNAL_LOCK_STATE, DATA_IS_CHARGING, DATA_IS_PLUGGED
from .sensor import HeidelbergEntity


@dataclass(frozen=True, kw_only=True)
class HeidelbergBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Heidelberg binary sensor entities."""


BINARY_SENSOR_TYPES: tuple[HeidelbergBinarySensorEntityDescription, ...] = (
    HeidelbergBinarySensorEntityDescription(
        key=DATA_EXTERNAL_LOCK_STATE,
        translation_key=DATA_EXTERNAL_LOCK_STATE,
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeidelbergBinarySensorEntityDescription(
        key=DATA_IS_PLUGGED,
        translation_key=DATA_IS_PLUGGED,
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    HeidelbergBinarySensorEntityDescription(
        key=DATA_IS_CHARGING,
        translation_key=DATA_IS_CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeidelbergEnergyControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        HeidelbergBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_TYPES
    )


class HeidelbergBinarySensor(HeidelbergEntity, BinarySensorEntity):
    """Representation of a Heidelberg Binary Sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return bool(self.coordinator.data.get(self.entity_description.key, False))
