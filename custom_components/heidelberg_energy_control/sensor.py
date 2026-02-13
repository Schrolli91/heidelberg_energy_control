"""Sensor platform for Heidelberg Energy Control integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HeidelbergEnergyControlConfigEntry
from .const import (
    COMMAND_MAX_CURRENT,
    DATA_CHARGING_POWER,
    DATA_CHARGING_STATE,
    DATA_CURRENT,
    DATA_CURRENT_L1,
    DATA_CURRENT_L2,
    DATA_CURRENT_L3,
    DATA_ENERGY_SINCE_POWER_ON,
    DATA_IS_PLUGGED,
    DATA_PCB_TEMPERATURE,
    DATA_PHASES_ACTIVE,
    DATA_SESSION_ENERGY,
    DATA_TOTAL_ENERGY,
    DATA_VOLTAGE_L1,
    DATA_VOLTAGE_L2,
    DATA_VOLTAGE_L3,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
)
from .coordinator import HeidelbergEnergyControlCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HeidelbergSensorEntityDescription(SensorEntityDescription):
    """Class describing Heidelberg sensor entities."""


SENSOR_TYPES: tuple[HeidelbergSensorEntityDescription, ...] = (
    HeidelbergSensorEntityDescription(
        key=DATA_CHARGING_STATE,
        translation_key=DATA_CHARGING_STATE,
        icon="mdi:ev-station",
        entity_category=EntityCategory.DIAGNOSTIC,
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
        key=COMMAND_MAX_CURRENT,
        translation_key=COMMAND_MAX_CURRENT,
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
        if description.key == DATA_TOTAL_ENERGY:
            entities.append(
                HeidelbergTotalEnergySensor(coordinator, entry, description)
            )
        elif description.key == "session_energy":
            entities.append(
                HeidelbergSessionEnergySensor(coordinator, entry, description)
            )
        else:
            entities.append(HeidelbergSensor(coordinator, entry, description))

    async_add_entities(entities)


class HeidelbergEntity(CoordinatorEntity[HeidelbergEnergyControlCoordinator]):
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


class HeidelbergSensor(HeidelbergEntity, SensorEntity):
    """Base class for standard Heidelberg sensors."""

    @property
    def icon(self) -> str | None:
        """Dynamically return the icon based on the state."""
        if self.entity_description.key == DATA_PHASES_ACTIVE:
            return f"mdi:numeric-{int(self.native_value or 0)}-box-outline"

        return self.entity_description.icon

    @property
    def native_value(self) -> Any:
        """Return value from coordinator."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)


class HeidelbergEnergyBaseSensor(HeidelbergEntity, RestoreEntity, SensorEntity):
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
            self._total_offset = last_state.attributes.get("_total_offset", 0.0)
            self._last_raw_value = last_state.attributes.get("_last_raw_value")
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


class HeidelbergTotalEnergySensor(HeidelbergEnergyBaseSensor):
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


class HeidelbergSessionEnergySensor(HeidelbergEnergyBaseSensor):
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
