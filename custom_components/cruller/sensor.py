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
from homeassistant.const import (
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrullerConfigEntry
from .entity import CrullerEntity, rt4k_device_info

# The RetroTINK's power states (/api/v1/state rt4k.power). "unknown", and any state a later Cruller
# adds, reads as unknown.
POWER_STATES = ["on", "standby", "starting"]


@dataclass(frozen=True, kw_only=True)
class CrullerSensorDescription(SensorEntityDescription):
    """Describes a Cruller sensor and how to read its value from the state."""

    value_fn: Callable[[dict[str, Any]], Any]
    # Whether this Cruller has it: the board's own sensors are only in the state of a board that has
    # them (the Pico 2 W, firmware 0.4.4+), so they're added once they show up.
    exists_fn: Callable[[dict[str, Any]], bool] = lambda d: True
    # The RetroTINK's own (its device), not Cruller's.
    rt4k: bool = False


def _board_sensor(key: str) -> Callable[[dict[str, Any]], bool]:
    return lambda d: key in d.get("cruller", {})


SENSORS: tuple[CrullerSensorDescription, ...] = (
    CrullerSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.ENUM,
        options=POWER_STATES,
        value_fn=lambda d: p if (p := d.get("rt4k", {}).get("power")) in POWER_STATES else None,
        rt4k=True,
    ),
    # The RetroTINK's firmware, as it last said it (Cruller 0.5.0+ keeps it while it sleeps): also in
    # its device's info, but a sensor keeps its history (when it changed). Added once Cruller has seen
    # it: after it has seen the RetroTINK on once. Its model is in the device's info only.
    CrullerSensorDescription(
        key="rt4k_firmware",
        translation_key="rt4k_firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("rt4k", {}).get("firmware"),
        exists_fn=lambda d: "firmware" in d.get("rt4k", {}),
        rt4k=True,
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
    # The board's own sensors: its supply (the Pico 2 W's VSYS, USB's 5 V less its input diode, so
    # ~4.7-4.9 V on a good supply), the lowest read since it started, and its chip's temperature.
    CrullerSensorDescription(
        key="supply_voltage",
        translation_key="supply_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda d: d.get("cruller", {}).get("supply_v"),
        exists_fn=_board_sensor("supply_v"),
    ),
    CrullerSensorDescription(
        key="supply_min_voltage",
        translation_key="supply_min_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda d: d.get("cruller", {}).get("supply_min_v"),
        exists_fn=_board_sensor("supply_min_v"),
    ),
    CrullerSensorDescription(
        key="chip_temperature",
        translation_key="chip_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("cruller", {}).get("temperature_c"),
        exists_fn=_board_sensor("temperature_c"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrullerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cruller's sensors: those its state has now, and the others once it has them (a
    firmware update that brings the board's sensors needs no reload)."""
    coordinator = entry.runtime_data
    async_add_entities([UpdatesSensor(coordinator)])
    added: set[str] = set()

    @callback
    def add_new() -> None:
        new = [desc for desc in SENSORS if desc.key not in added and desc.exists_fn(coordinator.data)]
        added.update(desc.key for desc in new)
        if new:
            async_add_entities(CrullerSensor(coordinator, desc) for desc in new)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class CrullerSensor(CrullerEntity, SensorEntity):
    """A single value read from Cruller's state payload."""

    entity_description: CrullerSensorDescription

    def __init__(self, coordinator, description: CrullerSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.rt4k:
            self._attr_device_info = rt4k_device_info(coordinator)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


class UpdatesSensor(CrullerEntity, SensorEntity):
    """How the state reaches Home Assistant: "push" while Cruller's /api/v1/events flows,
    "polling" otherwise (a Cruller from before events, or its socket down)."""

    _attr_translation_key = "updates"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["push", "polling"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "updates")

    @property
    def native_value(self) -> str:
        return "push" if self.coordinator.pushing else "polling"
