"""Firmware update entity for Cruller.

Reports the running firmware version and the latest release published on GitHub,
so Home Assistant shows the current version and flags when a newer one exists.
It is notify-only: Cruller installs its updates from its own page (Cruller tab),
where it downloads the release from GitHub itself and falls back to the previous
version if the new one doesn't come up.
"""

from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrullerConfigEntry
from .entity import CrullerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrullerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cruller's firmware update entity."""
    async_add_entities([CrullerUpdate(entry.runtime_data)])


class CrullerUpdate(CrullerEntity, UpdateEntity):
    """Shows the installed firmware and the latest GitHub release."""

    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "firmware_update")

    @property
    def entity_picture(self) -> str | None:
        # Update entities default to the integration's brand image as their
        # picture, which takes precedence over the icon. This custom integration
        # is not in home-assistant/brands, so that image 404s and Home Assistant
        # shows an "icon not available" placeholder. Drop it so the mdi icon
        # from icons.json is used instead.
        return None

    @property
    def installed_version(self) -> str | None:
        # The polled version; fall back to what was read at setup.
        return self._cruller.get("sw_version") or self.coordinator.info.get("sw_version")

    @property
    def latest_version(self) -> str | None:
        # Until the latest release is known, report the installed one so Home
        # Assistant does not show a spurious update.
        return self.coordinator.latest_version or self.installed_version

    @property
    def release_url(self) -> str | None:
        return self.coordinator.latest_release_url
