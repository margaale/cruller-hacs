"""Constants for the Cruller integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "cruller"

# Config entry keys
CONF_HOST = "host"

# The API version this integration speaks (docs/API.md in the Cruller repository). Crullers announce
# theirs in the _rt4k._tcp TXT ("api=1"); a later version keeps v1's routes next to its own.
API_VERSION = 1

# How often the coordinator polls /api/v1/state without events (a Cruller from before
# /api/v1/events, or while its socket is down). Cruller serves one HTTP request at a time (its page,
# SD card transfers and firmware uploads share it), so the poll stays light; 10 s is quick enough to
# follow the RetroTINK's power in automations.
UPDATE_INTERVAL = timedelta(seconds=10)

# While /api/v1/events pushes the state, polling is only a safety net.
PUSH_UPDATE_INTERVAL = timedelta(seconds=60)

# The events socket: reconnect after this many seconds, doubling up to the most while it keeps failing.
RECONNECT_MIN_S = 5
RECONNECT_MAX_S = 60

# The board, by /api/v1/info's "platform", for the device's model.
BOARDS = {"rp2": "Pico 2 W", "esp32": "ESP32-S3"}

# The firmware's GitHub repository, used to detect a newer Cruller release.
GITHUB_REPO = "margaale/Cruller"
GITHUB_LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# How often to check GitHub for a newer firmware release (GitHub allows 60
# unauthenticated calls per hour; this stays well within that).
LATEST_CHECK_INTERVAL = timedelta(minutes=30)

# The RetroTINK 4K's firmware indexes in RetroTINK's repository, one per channel, for the RetroTINK
# firmware update entity: "## Version X (date)" headings, each with its changelog. The installed
# version is compared with the newest of its own channel.
RT4K_FIRMWARE_RAW = "https://raw.githubusercontent.com/RetroTINK-LLC/firmware/main/"
RT4K_FIRMWARE_PAGE = "https://github.com/RetroTINK-LLC/firmware/blob/main/"
RT4K_CHANNELS = {"release": "4k.md", "experimental": "4k-experimental.md"}
