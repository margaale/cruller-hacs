"""Firmware update entities: Cruller's own, and the RetroTINK 4K's.

Each reports the installed version and the newest one published, so Home Assistant shows the current
version and flags when a newer one exists. Both are notify-only: Cruller installs its own updates
from its page (Cruller tab), downloading the release from GitHub and falling back to the previous
version if the new one doesn't come up; the RetroTINK's firmware installs from the same page
(RetroTINK tab, Firmware), which writes it to the RetroTINK's SD card.
"""

from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrullerConfigEntry
from .const import RT4K_CHANNELS, RT4K_FIRMWARE_PAGE
from .entity import CrullerEntity
from .rt4k_firmware import Rt4kFirmware, channel_of, newest, version_key

# Home Assistant shows at most this much of a release summary.
SUMMARY_MAX = 255


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrullerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the update entities: Cruller's at once, the RetroTINK's once Cruller reports its
    firmware (Cruller 0.5.0+, after it has seen the RetroTINK on once)."""
    coordinator = entry.runtime_data
    async_add_entities([CrullerUpdate(coordinator)])
    added = False

    @callback
    def add_rt4k() -> None:
        nonlocal added
        if not added and coordinator.data.get("rt4k", {}).get("firmware"):
            added = True
            async_add_entities([Rt4kFirmwareUpdate(coordinator)])

    add_rt4k()
    entry.async_on_unload(coordinator.async_add_listener(add_rt4k))


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


class Rt4kFirmwareUpdate(CrullerEntity, UpdateEntity):
    """The RetroTINK 4K's firmware, as Cruller last heard it, and the newest in RetroTINK's index of
    the same channel (release or experimental)."""

    _attr_translation_key = "rt4k_firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "rt4k_firmware_update")

    @property
    def entity_picture(self) -> str | None:
        return None  # the mdi icon, as for Cruller's (see CrullerUpdate)

    @property
    def installed_version(self) -> str | None:
        return self._rt4k.get("firmware")

    def _channel(self) -> str:
        return channel_of(self.installed_version or "", self.coordinator.rt4k_indexes)

    def _newest(self) -> Rt4kFirmware | None:
        return newest(self.coordinator.rt4k_indexes.get(self._channel(), []))

    @property
    def latest_version(self) -> str | None:
        # Until the index is read, the installed one: no spurious update.
        f = self._newest()
        return f.version if f else self.installed_version

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        return version_key(latest_version) > version_key(installed_version)

    @property
    def release_summary(self) -> str | None:
        f = self._newest()
        if not f or not f.changelog or f.version == self.installed_version:
            return None
        return f.changelog if len(f.changelog) <= SUMMARY_MAX else f.changelog[: SUMMARY_MAX - 1] + "…"

    @property
    def release_url(self) -> str | None:
        return RT4K_FIRMWARE_PAGE + RT4K_CHANNELS[self._channel()]

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"channel": self._channel()}
