"""Fixtures for the Cruller tests: a Cruller answering /api/v1 as docs/API.md in its repository says."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant

from custom_components.cruller.api import CrullerClient, CrullerUnsupportedError
from custom_components.cruller.const import CONF_HOST, DOMAIN, GITHUB_LATEST_RELEASE_URL

pytest_plugins = "pytest_homeassistant_custom_component"

HOST = "10.0.0.5"
BOARD_ID = "E1C7E49F5FBA5DD8"

INFO: dict[str, Any] = {
    "id": BOARD_ID,
    "name": "Living",
    "hostname": "cruller-living",
    "sw_version": "0.4.2",
    "platform": "rp2",
    "api_version": 1,
}

STATE: dict[str, Any] = {
    "rt4k": {"connected": True, "power": "on"},
    "cruller": {"sw_version": "0.4.2", "uptime_s": 3600, "rssi": -52},
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/cruller in every test."""
    yield


@pytest.fixture(autouse=True)
def no_events(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Cruller without /api/v1/events (0.4.2), unless a test takes the events fixture: polling."""

    async def unsupported(self, types: str = "state"):
        raise CrullerUnsupportedError("Cruller has no /api/v1/events")
        yield  # an async generator, like the real one

    monkeypatch.setattr(CrullerClient, "async_events", unsupported)


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> asyncio.Queue:
    """What /api/v1/events pushes: put a dict to send it, an exception to break the socket, None to
    close it. Each connection reads from the same queue; reconnecting doesn't wait."""
    queue: asyncio.Queue = asyncio.Queue()

    async def from_queue(self, types: str = "state"):
        while True:
            item = await queue.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    monkeypatch.setattr(CrullerClient, "async_events", from_queue)
    monkeypatch.setattr("custom_components.cruller.coordinator.RECONNECT_MIN_S", 0)
    monkeypatch.setattr("custom_components.cruller.coordinator.RECONNECT_MAX_S", 0)
    return queue


async def settle(hass: HomeAssistant) -> None:
    """Let the events listener (a background task, which async_block_till_done skips) take what's queued."""
    for _ in range(20):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


def mock_cruller(
    aioclient_mock: AiohttpClientMocker,
    *,
    state: dict[str, Any] | None = None,
    latest: str = "v0.4.1",
) -> None:
    """Register Cruller's GET routes, and GitHub's latest release."""
    aioclient_mock.get(f"http://{HOST}/api/v1/info", json=INFO)
    aioclient_mock.get(f"http://{HOST}/api/v1/state", json=state or STATE)
    aioclient_mock.get(
        GITHUB_LATEST_RELEASE_URL,
        json={"tag_name": latest, "html_url": f"https://github.com/margaale/Cruller/releases/tag/{latest}"},
    )


def state_with(**blocks: dict[str, Any]) -> dict[str, Any]:
    """STATE with some of its blocks' keys changed: state_with(rt4k={"power": "standby"})."""
    state = copy.deepcopy(STATE)
    for block, values in blocks.items():
        state[block].update(values)
    return state


async def setup_cruller(hass: HomeAssistant) -> MockConfigEntry:
    """Add a Cruller config entry and set it up."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}, unique_id=BOARD_ID, title="Cruller Living")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
