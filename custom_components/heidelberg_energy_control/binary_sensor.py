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
from .classes.heidelberg_binary_sensor import HeidelbergBinarySensor
from .const import DATA_EXTERNAL_LOCK_STATE, DATA_IS_CHARGING, DATA_IS_PLUGGED


@dataclass(frozen=True, kw_only=True)
class HeidelbergBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Heidelberg binary sensor entities."""

    min_version: str | None = None


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
    entities: list[BinarySensorEntity] = []

    for description in BINARY_SENSOR_TYPES:
        if coordinator.is_supported(description.min_version, description.key):
            entities.append(HeidelbergBinarySensor(coordinator, entry, description))

    async_add_entities(entities)
