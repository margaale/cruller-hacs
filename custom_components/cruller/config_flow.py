"""Config flow for the Cruller integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import CrullerClient, CrullerError, CrullerUnsupportedError, cruller_name
from .const import CONF_HOST, DOMAIN


class CrullerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cruller."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._discovered_name: str = "Cruller"

    async def _get_info(self, host: str) -> dict[str, Any]:
        """Return /api/v1/info, raising on connection problems or a firmware without it."""
        return await CrullerClient(async_get_clientsession(self.hass), host).async_get_info()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup: the user types Cruller's host."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                info = await self._get_info(host)
            except CrullerUnsupportedError:
                errors["base"] = "unsupported_firmware"
            except CrullerError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["id"])
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(title=cruller_name(info), data={CONF_HOST: host})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """A Cruller announced itself via mDNS (_rt4k._tcp): confirm it.

        Its firmware isn't checked here: one from before /api/v1 (TXT "api=/api") is still offered,
        and the confirmation says it needs an update, instead of never showing up.
        """
        self._host = discovery_info.host
        self._discovered_name = discovery_info.name.split(".")[0] or "Cruller"
        board_id = discovery_info.properties.get("id")
        if board_id:
            await self.async_set_unique_id(board_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask before adding a discovered Cruller."""
        errors: dict[str, str] = {}
        assert self._host is not None
        if user_input is not None:
            try:
                info = await self._get_info(self._host)
            except CrullerUnsupportedError:
                errors["base"] = "unsupported_firmware"
            except CrullerError:
                errors["base"] = "cannot_connect"
            else:
                if not self.unique_id:
                    await self.async_set_unique_id(info["id"])
                    self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
                return self.async_create_entry(title=cruller_name(info), data={CONF_HOST: self._host})

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._discovered_name, "host": self._host},
            errors=errors,
        )
