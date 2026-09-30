# Cruller — Home Assistant integration

A custom [Home Assistant](https://www.home-assistant.io/) integration for
**[Cruller](https://github.com/margaale/Cruller)**, the Pico 2 W that plugs into a
RetroTINK 4K's USB-C port and puts it on your network. Use it to power the RetroTINK
on and off, press its remote's buttons from automations, and react to what's on
screen: the SVS switch's active input, when an SVS Bridge reports it.

The integration is **local polling** only: it talks to Cruller over your LAN (its
`/api/v1`, every 10 s), with no cloud and no MQTT.

## Entities

Once set up, Cruller appears as a single device with:

| Entity | Type | Notes |
| --- | --- | --- |
| **RetroTINK 4K** | remote | On while the RetroTINK is on (or starting), off in standby. Turn it on or off, and send its remote's buttons (below). Unavailable while the RetroTINK isn't plugged into Cruller. |
| **RetroTINK power** | sensor | `On`, `Standby` or `Starting`, as Cruller reads it from the RetroTINK. |
| **Active input** | sensor | The SVS's active input number, once an SVS Bridge reports it (`unknown` while no input is active). |
| **Active input name** | sensor | That input's name, as the SVS Bridge calls it. |
| **RetroTINK connected** | binary sensor | Whether the RetroTINK is on Cruller's USB port. |
| **Firmware** | update | Cruller's running firmware, and whether a newer GitHub release exists. Notify-only; install from Cruller's page. |
| **Signal strength** | sensor (diagnostic, disabled by default) | Cruller's Wi-Fi RSSI. |

### The remote

`remote.send_command` takes the remote's keys by the RetroTINK's names (`menu`, `up`,
`down`, `left`, `right`, `ok`, `back`, `input`, `output`, `scaler`, `prof1`…), plus
`power_on` and `power_off`, or RetroTINK console commands, which have a space
(`remote menu`, `pwr on`). They go out one at a time, in order:

```yaml
action: remote.send_command
target:
  entity_id: remote.cruller_retrotink_4k
data:
  command: [menu, down, ok]
  delay_secs: 0.3
```

### An automation

Power the RetroTINK on when a console comes on screen:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.cruller_active_input
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.state not in ['unknown', 'unavailable'] }}"
actions:
  - action: remote.turn_on
    target:
      entity_id: remote.cruller_retrotink_4k
```

## Requirements

A Cruller with its versioned API (`/api/v1`), which came after firmware 0.4.1. An
older one is still discovered, and Home Assistant asks you to update it first: open
its page, **Cruller** tab, and install the latest release.

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
