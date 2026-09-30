"""Tests of the events socket (/api/v1/events): pushed state, polling as a safety net, reconnecting."""

from __future__ import annotations

import asyncio

from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.cruller.api import CrullerError
from custom_components.cruller.const import DOMAIN, PUSH_UPDATE_INTERVAL, UPDATE_INTERVAL

from .conftest import BOARD_ID, mock_cruller, settle, setup_cruller, state_with

HELLO = {"type": "hello", "api_version": 1, "types": ["state"], "subscribed": ["state"]}


def remote_state(hass: HomeAssistant) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("remote", DOMAIN, f"{BOARD_ID}_rt4k")
    return hass.states.get(entity_id).state


def updates(hass: HomeAssistant) -> str:
    """The "Updates" diagnostic sensor: push or polling."""
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{BOARD_ID}_updates")
    return hass.states.get(entity_id).state


async def test_pushed_state(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, events: asyncio.Queue) -> None:
    """Each state Cruller pushes updates the entities at once; polling slows to a safety net."""
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    coordinator = entry.runtime_data
    assert remote_state(hass) == STATE_ON

    events.put_nowait(HELLO)
    events.put_nowait({"type": "state", "state": state_with(rt4k={"power": "standby"})})
    await settle(hass)
    assert remote_state(hass) == STATE_OFF
    assert coordinator.update_interval == PUSH_UPDATE_INTERVAL
    assert updates(hass) == "push"

    # A type a later Cruller could send (to sockets that ask for it) changes nothing.
    events.put_nowait({"type": "later", "anything": [1, 2]})
    events.put_nowait({"type": "state", "state": state_with(rt4k={"power": "on"})})
    await settle(hass)
    assert remote_state(hass) == STATE_ON


async def test_pushed_new_version_checks_again(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, events: asyncio.Queue
) -> None:
    """Cruller back from an update pushes its new version: the latest release is read again at once,
    not at the next poll (a minute away while pushing)."""
    mock_cruller(aioclient_mock, latest="v0.4.2")
    await setup_cruller(hass)
    aioclient_mock.clear_requests()
    mock_cruller(aioclient_mock, latest="v0.5.0")
    events.put_nowait(HELLO)
    events.put_nowait({"type": "state", "state": state_with(cruller={"sw_version": "0.5.0"})})
    await settle(hass)
    entity_id = er.async_get(hass).async_get_entity_id("update", DOMAIN, f"{BOARD_ID}_firmware_update")
    assert hass.states.get(entity_id).attributes["latest_version"] == "0.5.0"


async def test_socket_breaks_and_reconnects(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, events: asyncio.Queue
) -> None:
    """While the socket is down, polling speeds up again; once it's back, it slows down."""
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    coordinator = entry.runtime_data

    events.put_nowait(HELLO)
    await settle(hass)
    assert coordinator.update_interval == PUSH_UPDATE_INTERVAL
    assert updates(hass) == "push"  # the hello alone says so, before any state

    events.put_nowait(CrullerError("Cruller restarted"))
    await settle(hass)
    assert coordinator.update_interval == UPDATE_INTERVAL
    assert updates(hass) == "polling"

    events.put_nowait(HELLO)
    events.put_nowait({"type": "state", "state": state_with(rt4k={"power": "standby"})})
    await settle(hass)
    assert coordinator.update_interval == PUSH_UPDATE_INTERVAL
    assert remote_state(hass) == STATE_OFF

    # Cruller closing the socket is the same: poll until it's back.
    events.put_nowait(None)
    await settle(hass)
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_hello_without_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, events: asyncio.Queue
) -> None:
    """A socket that doesn't get "state" (not offered) leaves polling as it is."""
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    events.put_nowait({"type": "hello", "api_version": 1, "types": [], "subscribed": []})
    await settle(hass)
    assert entry.runtime_data.update_interval == UPDATE_INTERVAL


async def test_no_events(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A Cruller from before /api/v1/events (404): polled every 10 s, as before."""
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    await settle(hass)
    assert entry.runtime_data.update_interval == UPDATE_INTERVAL
    assert remote_state(hass) == STATE_ON
    assert updates(hass) == "polling"


async def test_unload_stops_listening(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, events: asyncio.Queue
) -> None:
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    events.put_nowait(HELLO)
    await settle(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await settle(hass)
    events.put_nowait({"type": "state", "state": state_with(rt4k={"power": "standby"})})
    await settle(hass)
    assert events.qsize() == 1  # nobody took it: the listener is gone
