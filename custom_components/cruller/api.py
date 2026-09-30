"""Thin async client for Cruller's HTTP API (/api/v1, docs/API.md in the Cruller repository)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from .const import DOMAIN


class CrullerError(Exception):
    """A request to Cruller failed."""


class CrullerUnsupportedError(CrullerError):
    """Cruller's firmware predates /api/v1 (HTTP 404): it needs an update."""


class CrullerNotConnectedError(CrullerError):
    """The RetroTINK isn't connected to Cruller (HTTP 503), so a command couldn't be sent."""


def cruller_name(info: dict[str, Any]) -> str:
    """The name Cruller announces itself with: "Cruller Living", or "Cruller" until it's named."""
    name = info.get("name")
    return f"Cruller {name}" if name else "Cruller"


def rt4k_identifier(info: dict[str, Any]) -> tuple[str, str]:
    """The RetroTINK's device, one per Cruller."""
    return (DOMAIN, f"{info['id']}_rt4k")


def rt4k_name(info: dict[str, Any]) -> str:
    """"RetroTINK 4K", or "RetroTINK 4K Living" behind a Cruller named Living (so two don't clash)."""
    name = info.get("name")
    return f"RetroTINK 4K {name}" if name else "RetroTINK 4K"


def rt4k_model(model: str | None) -> str:
    """The RetroTINK's model as Cruller reports it ("RT4K_Pro"), as its page shows it ("RT4K Pro")."""
    return model.replace("_", " ") if model else "RetroTINK 4K"


class CrullerClient:
    """Talks to a single Cruller over plain HTTP (a LAN device, without authentication)."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self._host = host
        self._base = f"http://{host}"

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with self._session.request(
                method, f"{self._base}{path}", json=body, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 404:
                    raise CrullerUnsupportedError(
                        f"Cruller doesn't know {path}: update its firmware from its page"
                    )
                if resp.status == 503:
                    raise CrullerNotConnectedError("The RetroTINK isn't connected to Cruller")
                if resp.status != 200:
                    raise CrullerError(f"{path} returned HTTP {resp.status}")
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CrullerError(f"Cannot reach Cruller: {err!r}") from err
        except ValueError as err:  # a body that isn't JSON
            raise CrullerError(f"{path} didn't answer JSON: {err}") from err

    async def async_get_info(self) -> dict[str, Any]:
        """Who this Cruller is (stable while it runs: read once at setup)."""
        return await self._request("GET", "/api/v1/info")

    async def async_get_state(self) -> dict[str, Any]:
        """The RetroTINK's power, the switch's input and Cruller's own state (polled)."""
        return await self._request("GET", "/api/v1/state")

    async def async_press(self, button: str) -> dict[str, Any]:
        """Press a remote button by its name ("menu", "power_on"...), as Cruller maps them."""
        return await self._request("POST", "/api/v1/command", {"button": button})

    async def async_run(self, command: str) -> dict[str, Any]:
        """Send a console command ("remote menu", "pwr on"...) and get its replies."""
        return await self._request("POST", "/api/v1/command", {"command": command})

    async def async_events(self, types: str = "state") -> AsyncIterator[dict[str, Any]]:
        """Cruller's events (GET /api/v1/events, a WebSocket): each message as it comes, "hello" first.

        Ends when Cruller closes the socket. Raises CrullerUnsupportedError on a firmware without
        events (HTTP 404), and CrullerError when the socket can't be opened or breaks.
        """
        url = f"ws://{self._host}/api/v1/events?types={types}"
        try:
            # Cruller pings every 10 s (aiohttp answers); the heartbeat notices a Cruller that's gone.
            async with self._session.ws_connect(url, heartbeat=20) as ws:
                async for msg in ws:
                    if msg.type is aiohttp.WSMsgType.TEXT:
                        try:
                            event = json.loads(msg.data)
                        except ValueError:
                            continue
                        if isinstance(event, dict):
                            yield event
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
        except aiohttp.WSServerHandshakeError as err:
            if err.status == 404:
                raise CrullerUnsupportedError("Cruller has no /api/v1/events: update its firmware") from err
            raise CrullerError(f"Cruller refused the events socket: HTTP {err.status}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CrullerError(f"Cruller's events socket: {err!r}") from err
