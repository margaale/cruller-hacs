"""Sensor entities for Cruller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrullerConfigEntry
from .entity import CrullerEntity

# The RetroTINK's power states (/api/v1/state rt4k.power). "unknown", and any state a later Cruller
# adds, reads as unknown.
POWER_STATES = ["on", "standby", "starting"]


@dataclass(frozen=True, kw_only=True)
class CrullerSensorDescription(SensorEntityDescription):
    """Describes a Cruller sensor and how to read its value from the state."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[CrullerSensorDescription, ...] = (
    CrullerSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.ENUM,
        options=POWER_STATES,
        value_fn=lambda d: p if (p := d.get("rt4k", {}).get("power")) in POWER_STATES else None,
    ),
    CrullerSensorDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("cruller", {}).get("rssi"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrullerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cruller's sensors."""
    coordinator = entry.runtime_data
    async_add_entities(CrullerSensor(coordinator, desc) for desc in SENSORS)


class CrullerSensor(CrullerEntity, SensorEntity):
    """A single value read from Cruller's state payload."""

    entity_description: CrullerSensorDescription

    def __init__(self, coordinator, description: CrullerSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)
