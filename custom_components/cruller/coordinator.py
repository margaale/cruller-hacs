"""Polling coordinator for Cruller."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CrullerClient, CrullerError
from .const import DOMAIN, GITHUB_LATEST_RELEASE_URL, LATEST_CHECK_INTERVAL, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class CrullerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches /api/v1/state on a fixed interval and shares it with entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: CrullerClient,
        info: dict[str, Any],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.info = info  # static /api/v1/info payload
        # Latest firmware release on GitHub (checked occasionally, not every poll).
        self.latest_version: str | None = None
        self.latest_release_url: str | None = None
        self._latest_checked: datetime | None = None
        self._github = async_get_clientsession(hass)
        self._device_version: str | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.async_get_state()
        except CrullerError as err:
            raise UpdateFailed(str(err)) from err

        self._update_device_version(data)
        await self._maybe_check_latest()
        return data

    @callback
    def async_set_power(self, power: str | None) -> None:
        """Take the RetroTINK's power from a command's answer, without waiting for the next poll."""
        if not power or self.data is None:
            return
        rt4k = self.data.get("rt4k", {})
        if rt4k.get("power") == power:
            return
        self.async_set_updated_data({**self.data, "rt4k": {**rt4k, "power": power}})

    def _update_device_version(self, data: dict[str, Any]) -> None:
        """Keep the device's firmware version current as Cruller reports it (it updates itself)."""
        version = data.get("cruller", {}).get("sw_version")
        if not version or version == self._device_version:
            return
        self._device_version = version
        device = dr.async_get(self.hass).async_get_device(identifiers={(DOMAIN, self.info["id"])})
        if device is not None:
            dr.async_get(self.hass).async_update_device(device.id, sw_version=version)

    async def _maybe_check_latest(self) -> None:
        """Check GitHub for a newer firmware release, at most every 30 minutes."""
        now = dt_util.utcnow()
        if self._latest_checked is not None and now - self._latest_checked < LATEST_CHECK_INTERVAL:
            return
        self._latest_checked = now  # set first, so a failure does not retry in a loop
        try:
            async with self._github.get(
                GITHUB_LATEST_RELEASE_URL,
                headers={"Accept": "application/vnd.github+json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return
                body = await resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            _LOGGER.debug("Could not check GitHub for a newer firmware release", exc_info=True)
            return

        tag = (body.get("tag_name") or "").lstrip("v")
        if tag:
            self.latest_version = tag
            self.latest_release_url = body.get("html_url")
