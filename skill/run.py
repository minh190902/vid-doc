"""Launcher: runs `vid-doc <args>` inside the tool's own venv, creating it on first use.

Any Python 3.10+ can start this file; it never imports third-party packages itself.
  python run.py setup --library D:/path/to/library
  python run.py find search pixel art dithering
"""
import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

REPO = Path(os.path.realpath(__file__)).parent.parent  # through the ~/.claude/skills junction


def venv_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "vid-doc" / "venv"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "vid-doc" / "venv"


def venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install_stamp() -> str:
    """Changes when the repo moves or its dependencies change, so the venv is reinstalled then."""
    pyproject = (REPO / "pyproject.toml").read_bytes()
    return f"{REPO}\n{hashlib.sha256(pyproject).hexdigest()}"


def ensure_venv() -> Path:
    root = venv_dir()
    python = venv_python(root)
    marker = root / ".installed-from"
    stamp = install_stamp()
    if python.exists() and marker.exists() and marker.read_text(encoding="utf-8") == stamp:
        return python
    print(f"[vid-doc] installing dependencies into {root} (a few minutes the first time)...", flush=True)
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(root)
    subprocess.check_call([str(python), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    subprocess.check_call([str(python), "-m", "pip", "install", "-q", "-e", str(REPO)])
    marker.write_text(stamp, encoding="utf-8")
    return python


def main() -> int:
    if sys.version_info < (3, 10):
        sys.exit("vid-doc needs Python 3.10 or newer")
    python = ensure_venv()
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.call([str(python), "-m", "viddoc", *sys.argv[1:]], env=env)


if __name__ == "__main__":
    sys.exit(main())
