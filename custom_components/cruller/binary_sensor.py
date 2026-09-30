"""Binary sensor entities for Cruller."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrullerConfigEntry
from .entity import CrullerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrullerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cruller's binary sensors. USB power is the board's own sensor: added once the state
    has it (the Pico 2 W, firmware 0.4.4+), like sensor.py's."""
    coordinator = entry.runtime_data
    async_add_entities([Rt4kConnectedBinarySensor(coordinator)])
    added = False

    @callback
    def add_usb_power() -> None:
        nonlocal added
        if not added and "usb_power" in coordinator.data.get("cruller", {}):
            added = True
            async_add_entities([UsbPowerBinarySensor(coordinator)])

    add_usb_power()
    entry.async_on_unload(coordinator.async_add_listener(add_usb_power))


class Rt4kConnectedBinarySensor(CrullerEntity, BinarySensorEntity):
    """Whether the RetroTINK is on Cruller's USB port, its serial link up."""

    _attr_translation_key = "rt4k_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "rt4k_connected")

    @property
    def is_on(self) -> bool:
        return bool(self._rt4k.get("connected"))


class UsbPowerBinarySensor(CrullerEntity, BinarySensorEntity):
    """Whether USB brings Cruller 5 V (off: powered through VSYS)."""

    _attr_translation_key = "usb_power"
    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "usb_power")

    @property
    def is_on(self) -> bool | None:
        value = self._cruller.get("usb_power")
        return None if value is None else bool(value)
