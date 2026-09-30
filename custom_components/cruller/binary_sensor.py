"""Binary sensor entities for Cruller."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrullerConfigEntry
from .entity import CrullerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrullerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cruller's binary sensors."""
    async_add_entities([Rt4kConnectedBinarySensor(entry.runtime_data)])


class Rt4kConnectedBinarySensor(CrullerEntity, BinarySensorEntity):
    """Whether the RetroTINK is on Cruller's USB port, its serial link up."""

    _attr_translation_key = "rt4k_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "rt4k_connected")

    @property
    def is_on(self) -> bool:
        return bool(self._rt4k.get("connected"))
