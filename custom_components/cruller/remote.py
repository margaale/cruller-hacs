"""The RetroTINK's remote, through Cruller.

Turning it on and off follows the power state Cruller reads from the RetroTINK. Commands are the
remote's buttons by name ("menu", "up", "power_on"...), or console commands, which have a space
("remote menu", "pwr on"): Cruller sends them one at a time, in order.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrullerConfigEntry
from .api import CrullerError, CrullerNotConnectedError
from .entity import CrullerEntity

# Power states that count as on: "starting" is the RetroTINK powering on after "pwr on".
POWER_ON = ("on", "starting")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrullerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the RetroTINK's remote."""
    async_add_entities([CrullerRemote(entry.runtime_data)])


class CrullerRemote(CrullerEntity, RemoteEntity):
    """Powers the RetroTINK on and off and presses its remote's buttons."""

    _attr_translation_key = "rt4k"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "rt4k")

    @property
    def available(self) -> bool:
        # Without the RetroTINK on its USB port, Cruller can't send it anything.
        return super().available and bool(self._rt4k.get("connected"))

    @property
    def is_on(self) -> bool | None:
        power = self._rt4k.get("power")
        if power in POWER_ON:
            return True
        return False if power == "standby" else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send("power_on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send("power_off")

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        commands = list(command)
        for i in range(repeats):
            for j, cmd in enumerate(commands):
                if i or j:
                    await asyncio.sleep(delay)
                await self._send(cmd)

    async def _send(self, cmd: str) -> None:
        """A button by name, or a console command (it has a space)."""
        client = self.coordinator.client
        try:
            if " " in cmd.strip():
                answer = await client.async_run(cmd.strip())
            else:
                answer = await client.async_press(cmd.strip())
        except CrullerNotConnectedError as err:
            raise HomeAssistantError(str(err)) from err
        except CrullerError as err:
            raise HomeAssistantError(f"Cruller didn't take {cmd!r}: {err}") from err
        self.coordinator.async_set_power(answer.get("power"))
