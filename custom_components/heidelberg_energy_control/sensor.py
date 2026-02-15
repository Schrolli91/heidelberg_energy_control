"""Sensor platform for Heidelberg Energy Control integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .classes.heidelberg_sensor import HeidelbergSensor
from .classes.heidelberg_sensor_active_phases import HeidelbergSensorActivePhases
from .classes.heidelberg_sensor_energy_session import HeidelbergSensorEnergySession
from .classes.heidelberg_sensor_energy_total import HeidelbergSensorEnergyTotal
from .const import (
    COMMAND_TARGET_CURRENT,
    DATA_CHARGING_POWER,
    DATA_CHARGING_STATE,
    DATA_CURRENT,
    DATA_CURRENT_L1,
    DATA_CURRENT_L2,
    DATA_CURRENT_L3,
    DATA_ENERGY_SINCE_POWER_ON,
    DATA_PCB_TEMPERATURE,
    DATA_PHASES_ACTIVE,
    DATA_SESSION_ENERGY,
    DATA_TOTAL_ENERGY,
    DATA_VOLTAGE_L1,
    DATA_VOLTAGE_L2,
    DATA_VOLTAGE_L3,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HeidelbergSensorEntityDescription(SensorEntityDescription):
    """Class describing Heidelberg sensor entities."""

    min_version: str | None = None


SENSOR_TYPES: tuple[HeidelbergSensorEntityDescription, ...] = (
    HeidelbergSensorEntityDescription(
        key=DATA_CHARGING_STATE,
        translation_key=DATA_CHARGING_STATE,
        icon="mdi:ev-station",
        entity_category=EntityCategory.DIAGNOSTIC,
        # min_version="1.1.0",
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_CHARGING_POWER,
        translation_key=DATA_CHARGING_POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_TOTAL_ENERGY,
        translation_key=DATA_TOTAL_ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_SESSION_ENERGY,
        translation_key=DATA_SESSION_ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_ENERGY_SINCE_POWER_ON,
        translation_key=DATA_ENERGY_SINCE_POWER_ON,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_CURRENT,
        translation_key=DATA_CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_CURRENT_L1,
        translation_key=DATA_CURRENT_L1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_CURRENT_L2,
        translation_key=DATA_CURRENT_L2,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_CURRENT_L3,
        translation_key=DATA_CURRENT_L3,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_VOLTAGE_L1,
        translation_key=DATA_VOLTAGE_L1,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_VOLTAGE_L2,
        translation_key=DATA_VOLTAGE_L2,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_VOLTAGE_L3,
        translation_key=DATA_VOLTAGE_L3,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_PHASES_ACTIVE,
        translation_key=DATA_PHASES_ACTIVE,
        icon="mdi:numeric-3-box-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=DATA_PCB_TEMPERATURE,
        translation_key=DATA_PCB_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    HeidelbergSensorEntityDescription(
        key=COMMAND_TARGET_CURRENT,
        translation_key=COMMAND_TARGET_CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeidelbergEnergyControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for description in SENSOR_TYPES:
        if coordinator.is_supported(description.min_version, description.key):
            if description.key == DATA_TOTAL_ENERGY:
                entities.append(
                    HeidelbergSensorEnergyTotal(coordinator, entry, description)
                )
            elif description.key == DATA_SESSION_ENERGY:
                entities.append(
                    HeidelbergSensorEnergySession(coordinator, entry, description)
                )
            elif description.key == DATA_PHASES_ACTIVE:
                entities.append(
                    HeidelbergSensorActivePhases(coordinator, entry, description)
                )
            else:
                entities.append(HeidelbergSensor(coordinator, entry, description))

    async_add_entities(entities)
