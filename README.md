# Cruller — Home Assistant integration

A custom [Home Assistant](https://www.home-assistant.io/) integration for
**[Cruller](https://github.com/margaale/Cruller)**, the Pico 2 W that plugs into a
RetroTINK 4K's USB-C port and puts it on your network. Use it to power the RetroTINK
on and off, press its remote's buttons and load its profiles from automations, and
react to its power as it changes.

The integration is **local push**: Cruller tells Home Assistant as soon as the
RetroTINK's power changes (its `/api/v1/events`), over your LAN, with no cloud and no
MQTT. With a Cruller from before events (0.4.2), it polls every 10 s instead.

The SVS switch's input isn't here: the [SVS Bridge's integration](https://github.com/margaale/svs-bridge-hacs)
has it, straight from the bridge.

## Entities

Once set up, you get two devices: **Cruller**, and the **RetroTINK 4K** connected through it (named
after Cruller's: "RetroTINK 4K Living" behind "Cruller Living"). The RetroTINK's device shows its
model (`RT4K Pro`) and firmware version in its info, once Cruller has reported them.

**RetroTINK 4K:**

| Entity | Type | Notes |
| --- | --- | --- |
| *(the device's name)* | remote | On while the RetroTINK is on (or starting), off in standby. Turn it on or off, and send its remote's buttons (below). Unavailable while the RetroTINK isn't plugged into Cruller. |
| **Power** | sensor | `On`, `Standby` or `Starting`, as Cruller reads it from the RetroTINK. |
| **Firmware** | update | The RetroTINK's firmware, and whether a newer one is in [RetroTINK's firmware repository](https://github.com/RetroTINK-LLC/firmware), on the same channel as the installed one (Release, or Experimental for an experimental build: its `channel` attribute). Notify-only; install from Cruller's page (RetroTINK tab, Firmware). |
| **Firmware version** | sensor (diagnostic) | The RetroTINK's firmware version, with its history (when it changed). |

**Cruller:**

| Entity | Type | Notes |
| --- | --- | --- |
| **RetroTINK connected** | binary sensor | Whether the RetroTINK is on Cruller's USB port. |
| **Firmware** | update | Cruller's running firmware, and whether a newer GitHub release exists. Notify-only; install from Cruller's page. |
| **Updates** | sensor (diagnostic) | `Push` while Cruller pushes its state (instant), `Polling` otherwise (every 10 s: a Cruller from before events, or its socket down). |
| **Signal strength** | sensor (diagnostic, disabled by default) | Cruller's Wi-Fi RSSI. |
| **Supply voltage** | sensor (diagnostic) | Cruller's supply, in volts: the Pico 2 W's VSYS, USB's 5 V less its input diode, so ~4.7–4.9 V on a good supply. |
| **Lowest supply voltage** | sensor (diagnostic) | The lowest the supply read since Cruller started. A supply that sags when the RetroTINK draws more (switching inputs) shows here; one that sags too far resets Cruller. |
| **Chip temperature** | sensor (diagnostic) | Cruller's chip, in °C. |
| **USB power** | binary sensor (diagnostic) | Whether USB brings Cruller 5 V. |

The last four are the board's own sensors: a Pico 2 W with Cruller 0.4.4 or later. They appear on
their own once Cruller's state has them (after updating Cruller, no reload needed); an ESP32-S3
board doesn't have them.

The RetroTINK's firmware entities need Cruller 0.5.0 or later, and appear once Cruller has seen the
RetroTINK on (it keeps what it heard, so they stay while the RetroTINK sleeps). The integration
reads RetroTINK's firmware indexes when it checks for a new Cruller release, every 30 minutes, and
at once when Cruller's version or the RetroTINK's firmware changes.

Up to 0.4.0 everything was on Cruller's device. Updating moves the RetroTINK's entities to its own
device and keeps their entity ids (`remote.cruller_retrotink_4k`...), so automations keep working;
new installs get ids after the RetroTINK's device (`remote.retrotink_4k`), as in the examples below.
0.4.0's "RetroTINK model" sensor goes: the model is in the device's info.

### The remote

`remote.send_command` takes the remote's buttons by name, the same names as
[hass-RT4K](https://github.com/sjftech/hass-RT4K): the RetroTINK's own keys (`menu`, `up`,
`down`, `left`, `right`, `ok`, `back`, `input`, `prof1`…), their friendlier names
(`enter`, `diagnostics`, `profile1`, `1080p`, `auto_crop_16_9`…), `power_on` and
`power_off`. It also takes RetroTINK console commands, which have a space (`remote menu`,
`pwr on`). They go out one at a time, in order, so automations written for hass-RT4K
keep working:

```yaml
action: remote.send_command
target:
  entity_id: remote.retrotink_4k
data:
  command: [menu, down, ok]
  delay_secs: 0.3
```

### Automations

Load the SVS profile of the switch's input (`/profile/SVS/S3_….rt4` for input 3, with
"Auto Load SVS" on in the RetroTINK), sending it the same line the switch does. The
input comes from the [SVS Bridge's integration](https://github.com/margaale/svs-bridge-hacs):

```yaml
triggers:
  - trigger: state
    entity_id: sensor.svs_bridge_active_input
conditions:
  # No input active: the sensor is unknown, and nothing is sent.
  - condition: template
    value_template: "{{ trigger.to_state.state | int(0) > 0 }}"
actions:
  - action: remote.send_command
    target:
      entity_id: remote.retrotink_4k
    data:
      command: "SVS NEW INPUT={{ trigger.to_state.state | int }}"
```

Turn the TV on when the RetroTINK comes on:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.retrotink_4k_power
    to: "on"
actions:
  - action: media_player.turn_on
    target:
      entity_id: media_player.tv
```

## Requirements

A Cruller with its versioned API (`/api/v1`), which came after firmware 0.4.1; pushed
updates need one after 0.4.2 (before, the integration polls every 10 s). An older one is
still discovered, and Home Assistant asks you to update it first: open its page,
**Cruller** tab, and install the latest release.

## Installation

### HACS (recommended)

1. In HACS, add this repository as a **custom repository** (category: *Integration*).
2. Install **Cruller** and restart Home Assistant.

### Manual

Copy `custom_components/cruller` into your Home Assistant `config/custom_components/`
directory and restart.

## Setup

Cruller announces itself over mDNS, so Home Assistant usually **discovers it
automatically**, as "Cruller" or by its name ("Cruller Living"): look for a
notification and click *Add*. Home Assistant and Cruller need to be on the same
network, or on networks your router bridges mDNS between.

To add it manually: **Settings → Devices & services → Add integration → Cruller**, then
enter its host (`cruller.local`, `cruller-living.local` once it's named, or its IP address).

> Cruller has no passwords: anyone on your network can use its API, and so can Home
> Assistant, over plain HTTP. Keep it on a network you trust.

## Cruller's firmware

This repository holds only the Home Assistant integration. The firmware that runs on
Cruller, and its API's documentation
([docs/API.md](https://github.com/margaale/Cruller/blob/develop/docs/API.md)), live at
[margaale/Cruller](https://github.com/margaale/Cruller).
