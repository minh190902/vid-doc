"""YouTube through yt-dlp: search, channel tabs, metadata, download.

yt-dlp runs as a subprocess with the Deno it was installed with (YouTube needs a JS runtime since
yt-dlp 2025.11; Node < 22 is not supported). Facts measured 2026-10-16 are in docs/DESIGN.md.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.parse import quote_plus

from viddoc.config import tool

# YouTube search filters (the `sp` parameter). Both still worked on 2026-10-16.
DURATION_FILTERS = {
    "short": "EgIYAQ%253D%253D",  # under 4 minutes
    "medium": "EgIYAw%253D%253D",  # 4 to 20 minutes
}

def _video(*filters: str) -> list[str]:
    """Short side of the frame at most 480 px: a landscape clip by height, a vertical Short by width."""
    return [f"bv*{f}[height<=480][aspect_ratio>=1]/bv*{f}[width<=480][aspect_ratio<1]" for f in filters]


# Video and audio as separate files so no ffmpeg merge is needed. Measured 2026-10-16:
# - DASH (https) video of an 8:55 clip got HTTP 403 mid-download (needs a PO token); its HLS (m3u8)
#   stream downloaded whole. So HLS H.264 first, then DASH H.264, then anything.
# - The same clip carries 20 AI-dubbed audio tracks; take the one marked "original".
FORMAT = (
    "(" + "/".join(_video("[protocol^=m3u8][vcodec^=avc1]", "[vcodec^=avc1]", "")) + "/bv*)"
    ",(ba[format_note*=original]/ba[format_note!*=dubbed]/ba/b)"
)
BLOCK_MARKERS = ("Sign in to confirm", "confirm you're not a bot", "HTTP Error 429")
FORBIDDEN_MARKER = "HTTP Error 403"


class Blocked(RuntimeError):
    """YouTube refused the session (bot check, 429). Stop the batch; do not escalate."""


class Forbidden(RuntimeError):
    """HTTP 403 on one clip's media: usually that stream wants a PO token. Skip the clip."""


def search_url(query: str, length: str) -> str:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    return f"{url}&sp={DURATION_FILTERS[length]}" if length in DURATION_FILTERS else url


def channel_url(channel: str, tab: str) -> str:
    base = channel if channel.startswith("http") else f"https://www.youtube.com/{channel}"
    return f"{base.rstrip('/')}/{tab}"


def _run(args: list[str], timeout: int = 600) -> str:
    cmd = [tool("yt-dlp"), "--js-runtimes", f"deno:{tool('deno')}", "--no-warnings", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if any(marker in proc.stderr for marker in BLOCK_MARKERS):
        raise Blocked(proc.stderr.strip().splitlines()[-1])
    if FORBIDDEN_MARKER in proc.stderr:
        raise Forbidden(proc.stderr.strip().splitlines()[-1])
    # A failed -J run still prints "null"; only a run that produced something counts.
    if proc.returncode != 0 and proc.stdout.strip() in ("", "null"):
        raise RuntimeError(proc.stderr.strip()[-500:] or f"yt-dlp exited {proc.returncode}")
    return proc.stdout


def entry_from_flat(raw: dict, origin: str) -> dict | None:
    """One flat-playlist entry as a library candidate. Shorts lockups carry no duration or channel."""
    video_id = raw.get("id")
    if not video_id or raw.get("_type") not in (None, "url", "video"):
        return None
    return {
        "id": f"yt-{video_id}",
        "source": "youtube",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": raw.get("title") or "",
        "channel": raw.get("channel") or raw.get("uploader") or "",
        "duration": raw.get("duration"),
        "views": raw.get("view_count"),
        "origin": origin,
    }


def flat_list(url: str, limit: int, origin: str) -> list[dict]:
    out = _run(["--flat-playlist", "-J", "-I", f"1:{limit}", url])
    data = (json.loads(out) if out.strip() else None) or {}
    entries = [entry_from_flat(raw, origin) for raw in data.get("entries") or []]
    return [e for e in entries if e]


def search(query: str, limit: int, lengths: tuple[str, ...]) -> list[dict]:
    seen, found = set(), []
    for length in lengths:
        for entry in flat_list(search_url(query, length), limit, f"search:{query}:{length}"):
            if entry["id"] not in seen:
                seen.add(entry["id"])
                found.append(entry)
    return found


def channel_latest(channel: str, per_tab: int) -> list[dict]:
    found = []
    for tab in ("shorts", "videos"):
        try:
            for entry in flat_list(channel_url(channel, tab), per_tab, f"channel:{channel}:{tab}"):
                entry["channel"] = entry["channel"] or channel  # channel tabs do not repeat the name
                found.append(entry)
        except RuntimeError as error:  # a channel without that tab
            if "does not have" not in str(error):
                raise
    return found


def metadata(url: str) -> dict:
    return json.loads(_run(["-j", "--skip-download", url]))


def download(url: str, dest: Path) -> dict:
    """Video (short side <= 480) and audio as separate files, plus creator-uploaded subtitles.

    Auto-generated captions are not fetched: they mishear jargon and their translated tracks hit 429.
    Returns {"video": path, "audio": path or None, "subtitles": [paths]}.
    """
    dest.mkdir(parents=True, exist_ok=True)
    _run([
        "-t", "sleep", "-f", FORMAT,
        "--write-subs", "--no-write-auto-subs", "--sub-langs", "en.*,vi.*,-live_chat", "--sub-format", "vtt",
        "-o", str(dest / "%(format_id)s.%(ext)s"), "-o", f"subtitle:{dest / 'subs'}.%(ext)s",
        url,
    ], timeout=1800)
    files = sorted(p for p in dest.iterdir() if p.is_file())
    subtitles = [p for p in files if p.suffix == ".vtt"]
    media = [p for p in files if p.suffix not in (".vtt", ".part", ".ytdl")]
    video = next((p for p in media if _has_video(p)), None)
    if video is None:
        raise RuntimeError("download produced no video stream")
    audio = next((p for p in media if p != video), None)
    return {"video": video, "audio": audio, "subtitles": subtitles}


def _has_video(path: Path) -> bool:
    import cv2

    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    return bool(ok)
