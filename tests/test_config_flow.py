"""Tests of the Cruller config flow: by hand, and discovered over mDNS."""

from __future__ import annotations

from ipaddress import ip_address

import aiohttp

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.cruller.const import CONF_HOST, DOMAIN

from .conftest import BOARD_ID, HOST, INFO


def discovery(host: str = HOST, api: str = "1") -> ZeroconfServiceInfo:
    """What Home Assistant hands over when a Cruller announces _rt4k._tcp."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        port=80,
        hostname="cruller-living.local.",
        type="_rt4k._tcp.local.",
        name="Cruller Living._rt4k._tcp.local.",
        properties={"id": BOARD_ID, "ver": "0.4.2", "api": api, "name": "Living"},
    )


async def test_user(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"http://{HOST}/api/v1/info", json=INFO)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: f" {HOST} "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cruller Living"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == BOARD_ID


async def test_user_unnamed(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"http://{HOST}/api/v1/info", json={**INFO, "name": ""})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["title"] == "Cruller"


async def test_user_cannot_connect(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"http://{HOST}/api/v1/info", exc=aiohttp.ClientConnectionError())
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_timeout(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"http://{HOST}/api/v1/info", exc=TimeoutError())
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_old_firmware(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A Cruller from before /api/v1 answers 404: it needs an update."""
    aioclient_mock.get(f"http://{HOST}/api/v1/info", status=404, text="Not found\n")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["errors"] == {"base": "unsupported_firmware"}


async def test_user_already_configured(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "10.0.0.99"}, unique_id=BOARD_ID)
    entry.add_to_hass(hass)
    aioclient_mock.get(f"http://{HOST}/api/v1/info", json=INFO)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


async def test_zeroconf(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"http://{HOST}/api/v1/info", json=INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"name": "Cruller Living", "host": HOST}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cruller Living"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == BOARD_ID


async def test_zeroconf_new_address(hass: HomeAssistant) -> None:
    """A known Cruller that comes back with another address: the entry follows it."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "10.0.0.99"}, unique_id=BOARD_ID)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


async def test_zeroconf_old_firmware(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A Cruller from before /api/v1 (TXT api=/api) is still offered, and told to update."""
    aioclient_mock.get(f"http://{HOST}/api/v1/info", status=404, text="Not found\n")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery(api="/api")
    )
    assert result["step_id"] == "discovery_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_firmware"}
