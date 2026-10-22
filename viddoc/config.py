"""Where things live: the library (data), the tool's own venv, and the per-user config file."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

APP = "vid-doc"


def config_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP


def config_file() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    try:
        return json.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(config: dict) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    config_file().write_text(json.dumps(config, indent=2), encoding="utf-8")


def library_dir() -> Path:
    """`VIDDOC_LIBRARY`, else the configured library, else ~/vid-doc-library."""
    explicit = os.environ.get("VIDDOC_LIBRARY") or load_config().get("library")
    return Path(explicit) if explicit else Path.home() / "vid-doc-library"


def scripts_dir() -> Path:
    """The directory of the running interpreter's console scripts (the tool's venv)."""
    return Path(sys.executable).parent


def tool(name: str) -> str:
    """A console tool installed next to this interpreter (yt-dlp, deno), else one on PATH."""
    found = shutil.which(name, path=str(scripts_dir())) or shutil.which(name)
    if not found:
        raise SystemExit(f"{name} not found; run `vid-doc update` (or setup) to install it")
    return found
