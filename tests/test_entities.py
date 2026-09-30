"""Tests of Cruller's entities, from /api/v1/state, and the remote's commands."""

from __future__ import annotations

import aiohttp
import pytest

from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.remote import ATTR_COMMAND, ATTR_DELAY_SECS, ATTR_NUM_REPEATS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.cruller.const import DOMAIN

from .conftest import BOARD_ID, HOST, mock_cruller, setup_cruller, state_with

COMMAND_URL = f"http://{HOST}/api/v1/command"


def entity(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{BOARD_ID}_{key}")
    assert entity_id, f"no {platform} {key}"
    return entity_id


def value(hass: HomeAssistant, platform: str, key: str) -> str:
    return hass.states.get(entity(hass, platform, key)).state


def commands_sent(aioclient_mock: AiohttpClientMocker) -> list:
    return [data for method, url, data, _ in aioclient_mock.mock_calls if method == "POST" and str(url) == COMMAND_URL]


async def test_entities(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert value(hass, "remote", "rt4k") == STATE_ON
    assert value(hass, "sensor", "power") == "on"
    assert value(hass, "sensor", "active_input") == "3"
    assert value(hass, "sensor", "active_input_name") == "PS2"
    assert value(hass, "binary_sensor", "rt4k_connected") == STATE_ON
    # The signal strength is there, but off until the user turns it on.
    assert hass.states.get(entity(hass, "sensor", "rssi")) is None

    # Installed 0.4.2, GitHub's latest 0.4.1: nothing to update.
    update = hass.states.get(entity(hass, "update", "firmware_update"))
    assert update.state == STATE_OFF
    assert update.attributes["installed_version"] == "0.4.2"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, BOARD_ID)})
    assert device.name == "Cruller Living"
    assert device.model == "Cruller (Pico 2 W)"
    assert device.sw_version == "0.4.2"
    assert device.configuration_url == f"http://{HOST}"


async def test_update_available(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_cruller(aioclient_mock, latest="v0.5.0")
    await setup_cruller(hass)
    update = hass.states.get(entity(hass, "update", "firmware_update"))
    assert update.state == STATE_ON
    assert update.attributes["latest_version"] == "0.5.0"
    assert update.attributes["release_url"].endswith("/v0.5.0")


@pytest.mark.parametrize(
    ("svs", "active_input", "active_input_name"),
    [
        ({"input": 0, "name": ""}, STATE_UNKNOWN, STATE_UNKNOWN),  # no input active
        ({"input": 2, "name": ""}, "2", STATE_UNKNOWN),  # the port has no name
        ({"known": False}, STATE_UNKNOWN, STATE_UNKNOWN),  # no SVS Bridge has reported
    ],
)
async def test_svs_input(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, svs: dict, active_input: str, active_input_name: str
) -> None:
    mock_cruller(aioclient_mock, state=state_with(svs=svs))
    await setup_cruller(hass)
    assert value(hass, "sensor", "active_input") == active_input
    assert value(hass, "sensor", "active_input_name") == active_input_name


@pytest.mark.parametrize(
    ("power", "remote", "sensor"),
    [
        ("standby", STATE_OFF, "standby"),
        ("starting", STATE_ON, "starting"),
        ("unknown", STATE_UNKNOWN, STATE_UNKNOWN),
        ("hibernating", STATE_UNKNOWN, STATE_UNKNOWN),  # a state a later Cruller could add
    ],
)
async def test_power(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, power: str, remote: str, sensor: str) -> None:
    mock_cruller(aioclient_mock, state=state_with(rt4k={"power": power}))
    await setup_cruller(hass)
    assert value(hass, "remote", "rt4k") == remote
    assert value(hass, "sensor", "power") == sensor


async def test_rt4k_unplugged(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_cruller(aioclient_mock, state=state_with(rt4k={"connected": False, "power": "unknown"}))
    await setup_cruller(hass)
    assert value(hass, "binary_sensor", "rt4k_connected") == STATE_OFF
    assert value(hass, "remote", "rt4k") == STATE_UNAVAILABLE


async def test_turn_off_and_on(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The remote sends hass-RT4K's button names, and takes the power state from the answer."""
    mock_cruller(aioclient_mock)
    await setup_cruller(hass)
    remote = entity(hass, "remote", "rt4k")

    aioclient_mock.post(COMMAND_URL, json={"ok": True, "power": "standby", "results": []})
    await hass.services.async_call("remote", "turn_off", {ATTR_ENTITY_ID: remote}, blocking=True)
    assert commands_sent(aioclient_mock) == [{"button": "power_off"}]
    assert hass.states.get(remote).state == STATE_OFF

    aioclient_mock.clear_requests()
    mock_cruller(aioclient_mock)
    aioclient_mock.post(COMMAND_URL, json={"ok": True, "power": "starting", "results": []})
    await hass.services.async_call("remote", "turn_on", {ATTR_ENTITY_ID: remote}, blocking=True)
    assert commands_sent(aioclient_mock) == [{"button": "power_on"}]
    assert hass.states.get(remote).state == STATE_ON


async def test_send_command(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Button names go as buttons; anything with a space is a console command."""
    mock_cruller(aioclient_mock)
    await setup_cruller(hass)
    aioclient_mock.post(COMMAND_URL, json={"ok": True, "power": "on", "results": []})
    await hass.services.async_call(
        "remote",
        "send_command",
        {
            ATTR_ENTITY_ID: entity(hass, "remote", "rt4k"),
            ATTR_COMMAND: ["menu", "remote down"],
            ATTR_NUM_REPEATS: 2,
            ATTR_DELAY_SECS: 0,
        },
        blocking=True,
    )
    assert commands_sent(aioclient_mock) == [
        {"button": "menu"}, {"command": "remote down"}, {"button": "menu"}, {"command": "remote down"},
    ]


async def test_command_rt4k_not_connected(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Cruller answers 503 when it couldn't send a command: the service call fails, saying why."""
    mock_cruller(aioclient_mock)
    await setup_cruller(hass)
    aioclient_mock.post(COMMAND_URL, status=503, json={"ok": False, "power": "unknown", "results": []})
    with pytest.raises(HomeAssistantError, match="isn't connected"):
        await hass.services.async_call(
            "remote", "send_command", {ATTR_ENTITY_ID: entity(hass, "remote", "rt4k"), ATTR_COMMAND: ["menu"]},
            blocking=True,
        )


async def test_setup_retry(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"http://{HOST}/api/v1/info", exc=aiohttp.ClientConnectionError())
    entry = await setup_cruller(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_old_firmware(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"http://{HOST}/api/v1/info", status=404, text="Not found\n")
    entry = await setup_cruller(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
