"""Constants for the Cruller integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "cruller"

# Config entry keys
CONF_HOST = "host"

# The API version this integration speaks (docs/API.md in the Cruller repository). Crullers announce
# theirs in the _rt4k._tcp TXT ("api=1"); a later version keeps v1's routes next to its own.
API_VERSION = 1

# How often the coordinator polls /api/v1/state. Cruller serves one HTTP request at a time (its
# page, SD card transfers and firmware uploads share it), so the poll stays light; 10 s is quick
# enough to follow the RetroTINK's power in automations.
UPDATE_INTERVAL = timedelta(seconds=10)

# The board, by /api/v1/info's "platform", for the device's model.
BOARDS = {"rp2": "Pico 2 W", "esp32": "ESP32-S3"}

# The firmware's GitHub repository, used to detect a newer Cruller release.
GITHUB_REPO = "margaale/Cruller"
GITHUB_LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# How often to check GitHub for a newer firmware release (GitHub allows 60
# unauthenticated calls per hour; this stays well within that).
LATEST_CHECK_INTERVAL = timedelta(minutes=30)
