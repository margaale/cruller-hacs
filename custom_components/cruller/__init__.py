"""The Cruller integration: a RetroTINK 4K on the network, through Cruller."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CrullerClient, CrullerError, CrullerUnsupportedError
from .const import CONF_HOST, DOMAIN
from .coordinator import CrullerCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.REMOTE, Platform.SENSOR, Platform.UPDATE]

CrullerConfigEntry = ConfigEntry[CrullerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CrullerConfigEntry) -> bool:
    """Set up Cruller from a config entry."""
    client = CrullerClient(async_get_clientsession(hass), entry.data[CONF_HOST])

    try:
        info = await client.async_get_info()
    except CrullerUnsupportedError as err:
        raise ConfigEntryError(str(err)) from err
    except CrullerError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = CrullerCoordinator(hass, entry, client, info)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    # 0.4.0 had a "RetroTINK model" sensor; the model is in the RetroTINK device's info now.
    registry = er.async_get(hass)
    if old := registry.async_get_entity_id("sensor", DOMAIN, f"{info['id']}_rt4k_model"):
        registry.async_remove(old)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Pushed updates (/api/v1/events); cancelled when the entry unloads.
    entry.async_create_background_task(hass, coordinator.async_listen(), f"{entry.title} events")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CrullerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
