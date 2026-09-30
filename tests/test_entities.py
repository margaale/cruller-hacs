"""Tests of Cruller's entities, from /api/v1/state, and the remote's commands."""

from __future__ import annotations

import aiohttp
import pytest

from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.remote import ATTR_COMMAND, ATTR_DELAY_SECS, ATTR_NUM_REPEATS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
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


BOARD_SENSORS = {"supply_v": 4.84, "supply_min_v": 4.71, "usb_power": True, "temperature_c": 31.4}
BOARD_ENTITIES = [
    ("sensor", "supply_voltage"), ("sensor", "supply_min_voltage"), ("sensor", "chip_temperature"),
    ("binary_sensor", "usb_power"),
]


def registered(hass: HomeAssistant, platform: str, key: str) -> er.RegistryEntry | None:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{BOARD_ID}_{key}")
    return er.async_get(hass).async_get(entity_id) if entity_id else None


async def test_board_sensors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A Pico 2 W (0.4.4+): its supply, lowest supply, chip temperature and USB power, as diagnostics
    on the same device."""
    mock_cruller(aioclient_mock, state=state_with(cruller=BOARD_SENSORS))
    await setup_cruller(hass)
    assert value(hass, "sensor", "supply_voltage") == "4.84"
    assert value(hass, "sensor", "supply_min_voltage") == "4.71"
    assert value(hass, "sensor", "chip_temperature") == "31.4"
    assert value(hass, "binary_sensor", "usb_power") == STATE_ON
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, BOARD_ID)})
    for platform, key in BOARD_ENTITIES:
        reg = registered(hass, platform, key)
        assert reg.entity_category is EntityCategory.DIAGNOSTIC
        assert reg.device_id == device.id


async def test_no_board_sensors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """An ESP32-S3, or a Cruller from before 0.4.4: no board sensors at all, not unavailable ones."""
    mock_cruller(aioclient_mock)
    await setup_cruller(hass)
    for platform, key in BOARD_ENTITIES:
        assert registered(hass, platform, key) is None


async def test_board_sensors_appear(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Cruller updated to a firmware with the board's sensors: they appear with the next state, no
    reload."""
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    assert registered(hass, "sensor", "supply_voltage") is None
    aioclient_mock.clear_requests()
    mock_cruller(aioclient_mock, state=state_with(cruller=BOARD_SENSORS))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert value(hass, "sensor", "supply_voltage") == "4.84"
    assert value(hass, "binary_sensor", "usb_power") == STATE_ON


async def test_update_available(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_cruller(aioclient_mock, latest="v0.5.0")
    await setup_cruller(hass)
    update = hass.states.get(entity(hass, "update", "firmware_update"))
    assert update.state == STATE_ON
    assert update.attributes["latest_version"] == "0.5.0"
    assert update.attributes["release_url"].endswith("/v0.5.0")


async def test_cruller_updated_checks_again(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Cruller updated to a release published after the last check: its latest version is read again
    at once, not up to 30 minutes later (it showed "latest 0.4.4" next to "installed 0.5.0")."""
    mock_cruller(aioclient_mock, latest="v0.4.2")
    entry = await setup_cruller(hass)
    aioclient_mock.clear_requests()
    mock_cruller(aioclient_mock, state=state_with(cruller={"sw_version": "0.5.0"}), latest="v0.5.0")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    update = hass.states.get(entity(hass, "update", "firmware_update"))
    assert update.attributes["installed_version"] == "0.5.0"
    assert update.attributes["latest_version"] == "0.5.0"


async def test_same_version_no_recheck(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Polls with the same versions don't ask GitHub again within the 30 minutes."""
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    aioclient_mock.clear_requests()
    mock_cruller(aioclient_mock, latest="v0.9.0")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    update = hass.states.get(entity(hass, "update", "firmware_update"))
    assert update.attributes["latest_version"] == "0.4.1"  # what GitHub said at setup


async def test_rt4k_updated_checks_again(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The RetroTINK updated to a version published after the last check: the index is read again."""
    mock_cruller(aioclient_mock, state=state_with(rt4k={"firmware": "1.90.1"}))
    entry = await setup_cruller(hass)
    aioclient_mock.clear_requests()
    mock_cruller(aioclient_mock, state=state_with(rt4k={"firmware": "1.90.3"}), rt4k_experimental=("1.90.3", "1.90.2"))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    update = rt4k_update(hass)
    assert update.attributes["latest_version"] == "1.90.3"
    assert update.attributes["channel"] == "experimental"


RT4K_ENTITIES = [("remote", "rt4k"), ("sensor", "power"), ("sensor", "rt4k_firmware"), ("update", "rt4k_firmware_update")]
CRULLER_ENTITIES = [("binary_sensor", "rt4k_connected"), ("update", "firmware_update"), ("sensor", "updates")]


def rt4k_device(hass: HomeAssistant) -> dr.DeviceEntry:
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{BOARD_ID}_rt4k")})


async def test_rt4k_device(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The RetroTINK is its own device, through Cruller's: its model and firmware in its info (Cruller
    0.5.0+, also while it sleeps), its remote, power and firmware on it."""
    mock_cruller(aioclient_mock, state=state_with(rt4k={"power": "standby", "firmware": "1.89.0", "model": "RT4K_Pro"}))
    await setup_cruller(hass)
    cruller = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, BOARD_ID)})
    rt4k = rt4k_device(hass)
    assert rt4k.name == "RetroTINK 4K Living"  # behind "Cruller Living"
    assert rt4k.manufacturer == "RetroTINK"
    assert rt4k.model == "RT4K Pro"
    assert rt4k.sw_version == "1.89.0"
    assert rt4k.via_device_id == cruller.id
    for platform, key in RT4K_ENTITIES:
        assert registered(hass, platform, key).device_id == rt4k.id, key
    for platform, key in CRULLER_ENTITIES:
        assert registered(hass, platform, key).device_id == cruller.id, key
    # Named after its device: the remote is the device's main entity.
    assert entity(hass, "remote", "rt4k") == "remote.retrotink_4k_living"
    assert entity(hass, "sensor", "power") == "sensor.retrotink_4k_living_power"
    assert value(hass, "sensor", "rt4k_firmware") == "1.89.0"
    assert registered(hass, "sensor", "rt4k_firmware").entity_category is EntityCategory.DIAGNOSTIC
    # The firmware update is the user's, not a diagnostic (a notify-only update's default).
    assert registered(hass, "update", "rt4k_firmware_update").entity_category is None


async def test_rt4k_device_follows(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The device's firmware follows an update of the RetroTINK, and its model shows once known."""
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    assert rt4k_device(hass).model == "RetroTINK 4K"  # nothing reported yet (before 0.5.0)
    assert rt4k_device(hass).sw_version is None
    for firmware in ("1.89.0", "1.91.0"):
        aioclient_mock.clear_requests()
        mock_cruller(aioclient_mock, state=state_with(rt4k={"firmware": firmware, "model": "RT4K_CE"}))
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert rt4k_device(hass).sw_version == firmware
        assert rt4k_device(hass).model == "RT4K CE"


async def test_upgrade_keeps_entity_ids(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """From 0.4.0, where they were Cruller's: the RetroTINK's entities move to its device and keep
    their entity ids (automations and dashboards keep working)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.cruller.const import CONF_HOST

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}, unique_id=BOARD_ID, title="Cruller Living")
    entry.add_to_hass(hass)
    cruller = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, BOARD_ID)})
    old = {
        ("remote", "rt4k"): "remote.cruller_living_retrotink_4k",
        ("sensor", "power"): "sensor.cruller_living_retrotink_power",
        ("update", "rt4k_firmware_update"): "update.cruller_living_retrotink_firmware",
    }
    for (platform, key), entity_id in old.items():
        er.async_get(hass).async_get_or_create(
            platform, DOMAIN, f"{BOARD_ID}_{key}", suggested_object_id=entity_id.split(".")[1],
            config_entry=entry, device_id=cruller.id,
        )
    mock_cruller(aioclient_mock, state=state_with(rt4k={"firmware": "1.89.0", "model": "RT4K_Pro"}))
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for (platform, key), entity_id in old.items():
        assert entity(hass, platform, key) == entity_id
        assert registered(hass, platform, key).device_id == rt4k_device(hass).id
    assert hass.states.get("remote.cruller_living_retrotink_4k").state == STATE_ON


async def test_model_sensor_removed(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """0.4.0's "RetroTINK model" sensor goes: the model is in the device's info."""
    er.async_get(hass).async_get_or_create("sensor", DOMAIN, f"{BOARD_ID}_rt4k_model", suggested_object_id="old_model")
    mock_cruller(aioclient_mock, state=state_with(rt4k={"firmware": "1.89.0", "model": "RT4K_Pro"}))
    await setup_cruller(hass)
    assert registered(hass, "sensor", "rt4k_model") is None
    assert hass.states.get("sensor.old_model") is None


async def test_no_rt4k_firmware(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A Cruller from before 0.5.0, or one that hasn't seen the RetroTINK on yet: no such entities."""
    mock_cruller(aioclient_mock)
    await setup_cruller(hass)
    assert registered(hass, "sensor", "rt4k_firmware") is None
    assert registered(hass, "update", "rt4k_firmware_update") is None


def rt4k_update(hass: HomeAssistant):
    return hass.states.get(entity(hass, "update", "rt4k_firmware_update"))


@pytest.mark.parametrize(
    ("installed", "state", "latest", "channel"),
    [
        ("1.89.0", STATE_OFF, "1.89.0", "release"),        # the newest release
        ("1.87.3", STATE_ON, "1.89.0", "release"),         # an older release: the newest release
        ("1.90.1", STATE_ON, "1.90.2", "experimental"),    # an experimental build: the newest experimental
        ("1.90.2", STATE_OFF, "1.90.2", "experimental"),
        ("1.91.0", STATE_OFF, "1.90.2", "experimental"),   # newer than both lists (a beta): not older
        ("1.80.0", STATE_ON, "1.89.0", "release"),         # in neither list, older: release
    ],
)
async def test_rt4k_update(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, installed: str, state: str, latest: str, channel: str
) -> None:
    """The installed firmware is compared with the newest of its own channel."""
    mock_cruller(aioclient_mock, state=state_with(rt4k={"firmware": installed}))
    await setup_cruller(hass)
    update = rt4k_update(hass)
    assert update.state == state
    assert update.attributes["installed_version"] == installed
    assert update.attributes["latest_version"] == latest
    assert update.attributes["channel"] == channel
    assert update.attributes["release_url"].endswith("4k.md" if channel == "release" else "4k-experimental.md")
    if state == STATE_ON:
        assert update.attributes["release_summary"] == f"- What's new in {latest}"


async def test_rt4k_update_promoted(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A version in both lists (an experimental build made a release) follows the release channel."""
    mock_cruller(
        aioclient_mock, state=state_with(rt4k={"firmware": "1.89.0"}),
        rt4k_release=("1.89.0",), rt4k_experimental=("1.90.0", "1.89.0"),
    )
    await setup_cruller(hass)
    assert rt4k_update(hass).state == STATE_OFF
    assert rt4k_update(hass).attributes["channel"] == "release"


async def test_rt4k_update_no_index(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """RetroTINK's index can't be read: the installed version, no update shown."""
    mock_cruller(aioclient_mock, state=state_with(rt4k={"firmware": "1.87.3"}), rt4k_release=(), rt4k_experimental=())
    await setup_cruller(hass)
    assert rt4k_update(hass).state == STATE_OFF
    assert rt4k_update(hass).attributes["latest_version"] == "1.87.3"


async def test_rt4k_firmware_appears(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Cruller sees the RetroTINK on for the first time: its firmware entities appear, no reload."""
    mock_cruller(aioclient_mock)
    entry = await setup_cruller(hass)
    aioclient_mock.clear_requests()
    mock_cruller(aioclient_mock, state=state_with(rt4k={"firmware": "1.87.3", "model": "RT4K_Pro"}))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert value(hass, "sensor", "rt4k_firmware") == "1.87.3"
    assert rt4k_update(hass).state == STATE_ON


async def test_no_svs(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The SVS comes from the SVS Bridge's own integration: Cruller has no SVS entities."""
    mock_cruller(aioclient_mock)
    await setup_cruller(hass)
    ids = [e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), hass.config_entries.async_entries(DOMAIN)[0].entry_id)]
    assert not [i for i in ids if "input" in i or "svs" in i]


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
