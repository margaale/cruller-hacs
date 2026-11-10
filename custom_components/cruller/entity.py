"""Base entity for the Cruller integration."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import cruller_name, rt4k_identifier, rt4k_model, rt4k_name
from .const import BOARDS, CONF_HOST, DOMAIN
from .coordinator import CrullerCoordinator


class CrullerEntity(CoordinatorEntity[CrullerCoordinator]):
    """Common device info for all Cruller entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CrullerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        info = coordinator.info
        device_id = info["id"]
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = cruller_device_info(coordinator)

    @property
    def _rt4k(self) -> dict:
        """The 'rt4k' block of the latest /api/v1/state payload."""
        return self.coordinator.data.get("rt4k", {})

    @property
    def _cruller(self) -> dict:
        """The 'cruller' block of the latest /api/v1/state payload."""
        return self.coordinator.data.get("cruller", {})


def cruller_device_info(coordinator: CrullerCoordinator) -> DeviceInfo:
    """Cruller's own device."""
    info = coordinator.info
    host = coordinator.config_entry.data[CONF_HOST]
    board = BOARDS.get(info.get("platform", ""))
    return DeviceInfo(
        identifiers={(DOMAIN, info["id"])},
        name=cruller_name(info),
        manufacturer="Cruller",
        model=f"Cruller ({board})" if board else "Cruller",
        sw_version=info.get("sw_version"),
        configuration_url=f"http://{host}",
    )


def rt4k_device_info(coordinator: CrullerCoordinator) -> DeviceInfo:
    """The RetroTINK's own device, connected through Cruller's. Its model and firmware come from
    Cruller's state (0.5.0+) and follow it (coordinator.py)."""
    info = coordinator.info
    rt4k = (coordinator.data or {}).get("rt4k", {})
    return DeviceInfo(
        identifiers={rt4k_identifier(info)},
        name=rt4k_name(info),
        manufacturer="RetroTINK",
        model=rt4k_model(rt4k.get("model")),
        sw_version=rt4k.get("firmware"),
        # Cruller's device is registered before the platforms are set up (__init__.py).
        via_device_id=dr.async_get_device_id_by_identifier(
            coordinator.hass, (DOMAIN, info["id"]), config_entry_id=coordinator.config_entry.entry_id
        ),
    )


class Rt4kEntity(CrullerEntity):
    """An entity of the RetroTINK itself, on its device."""

    def __init__(self, coordinator: CrullerCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_device_info = rt4k_device_info(coordinator)
