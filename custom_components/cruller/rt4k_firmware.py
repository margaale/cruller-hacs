"""The RetroTINK 4K's firmware in RetroTINK's repository: its indexes, and which one to compare with.

RetroTINK publishes two channels, Release (4k.md) and Experimental (4k-experimental.md), each a
markdown page with a "## Version X (date)" heading per version and its changelog after "### Changelog"
(the same pages Cruller's firmware updater reads). The installed version is compared with the newest
of its own channel: a RetroTINK on an experimental build is told about the next experimental one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^## Version (\S+) \((\d{4}-\d\d-\d\d)\)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Rt4kFirmware:
    """One version in an index."""

    version: str
    date: str
    changelog: str


def version_key(version: str) -> tuple[int, ...]:
    """Versions compare by their numbers: 1.10.0 is newer than 1.9.2."""
    return tuple(int(n) for n in re.findall(r"\d+", version))


def parse_index(md: str) -> list[Rt4kFirmware]:
    """Every version in an index page, as it lists them."""
    heads = list(_HEADING.finditer(md))
    out = []
    for i, head in enumerate(heads):
        section = md[head.start():heads[i + 1].start() if i + 1 < len(heads) else len(md)]
        log = re.split(r"### Changelog:?", section, maxsplit=1)
        changelog = re.split(r"<br/?>|\n## ", log[1])[0].strip() if len(log) > 1 else ""
        out.append(Rt4kFirmware(head.group(1), head.group(2), changelog))
    return out


def channel_of(installed: str, indexes: dict[str, list[Rt4kFirmware]]) -> str:
    """The channel the installed version is on: experimental when it's only in that index (or in
    neither, and newer than every release), release otherwise."""
    release = indexes.get("release", [])
    experimental = indexes.get("experimental", [])
    in_release = any(f.version == installed for f in release)
    if any(f.version == installed for f in experimental) and not in_release:
        return "experimental"
    if not in_release and experimental and release:
        newest_release = max(version_key(f.version) for f in release)
        if version_key(installed) > newest_release:
            return "experimental"
    return "release"


def newest(firmware: list[Rt4kFirmware]) -> Rt4kFirmware | None:
    """The newest version of an index (by number, not by where it's listed)."""
    return max(firmware, key=lambda f: version_key(f.version), default=None)
