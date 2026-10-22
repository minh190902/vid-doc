"""The library: plain files any agent can read.

  inbox/             videos dropped by hand (Instagram, anything)
  items/<id>/        meta.json, media/ (deleted after notes), frames/, sheet-N.jpg, transcript.txt, notes.md
  index.json         id -> entry with a status
  channels.txt       channel handles or URLs to watch, one per line
  digests/           summaries written by the agent
  tips.md            the cumulative tip catalogue, written by the agent
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

# found -> picked -> fetched -> noted -> digested; rejected and failed are terminal until re-picked.
STATUSES = ("found", "picked", "rejected", "fetched", "noted", "digested", "failed")

DEFAULT_CHANNELS = """\
# One channel per line: @handle or a full channel URL. Lines starting with # are ignored.
# Pixel-art teachers (handles checked 2026-10-16). Their newest uploads are often devlogs, not tips;
# the agent shortlists before anything is fetched.
@MortMort
@AdamCYounis
@BJGpixel
@PeterMilko
@Retronator
@1BitStudio
@PixelOverloadChannel
@JustFredrik
@Goodgis
@apoxfox
@saultoons
"""

TIPS_HEADER = "# Tips catalogue\n\nOne entry per tip, merged across clips. Written by the agent from digests.\n"


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def slug(text: str, limit: int = 48) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text[:limit].rstrip("-") or "item"


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)

    # layout -----------------------------------------------------------------------------------
    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    @property
    def items(self) -> Path:
        return self.root / "items"

    @property
    def digests(self) -> Path:
        return self.root / "digests"

    @property
    def index_file(self) -> Path:
        return self.root / "index.json"

    @property
    def channels_file(self) -> Path:
        return self.root / "channels.txt"

    def item_dir(self, item_id: str) -> Path:
        return self.items / item_id

    def ensure(self) -> None:
        for path in (self.inbox, self.items, self.digests):
            path.mkdir(parents=True, exist_ok=True)
        if not self.channels_file.exists():
            self.channels_file.write_text(DEFAULT_CHANNELS, encoding="utf-8")
        tips = self.root / "tips.md"
        if not tips.exists():
            tips.write_text(TIPS_HEADER, encoding="utf-8")
        if not self.index_file.exists():
            self.save({})

    # index ------------------------------------------------------------------------------------
    def load(self) -> dict:
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save(self, index: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.index_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.index_file)

    def add_found(self, entries: list[dict]) -> list[dict]:
        """Record new candidates; ones already in the index (any status) are not returned."""
        index = self.load()
        fresh = []
        for entry in entries:
            if entry["id"] in index:
                continue
            entry = {**entry, "status": "found", "updated": now()}
            index[entry["id"]] = entry
            fresh.append(entry)
        self.save(index)
        return fresh

    def set_status(self, ids: list[str], status: str, **fields) -> list[str]:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status}")
        index = self.load()
        missing = [i for i in ids if i not in index]
        for item_id in ids:
            if item_id in index:
                index[item_id].update(fields, status=status, updated=now())
        self.save(index)
        return missing

    def update(self, item_id: str, **fields) -> None:
        index = self.load()
        index[item_id].update(fields, updated=now())
        self.save(index)

    def with_status(self, *statuses: str) -> list[dict]:
        return [e for e in self.load().values() if e.get("status") in statuses]

    def channels(self) -> list[str]:
        if not self.channels_file.exists():
            return []
        lines = self.channels_file.read_text(encoding="utf-8").splitlines()
        return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
