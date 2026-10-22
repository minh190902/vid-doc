"""One item's notes: key frames, a contact sheet, the transcript, and notes.md tying them together."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from viddoc.frames import clock, contact_sheets, key_frames, save_frames
from viddoc.transcript import Segment, Transcriber, parse_vtt


def link_at(meta: dict, t: float) -> str | None:
    if meta.get("source") == "youtube" and meta.get("video_id"):
        return f"https://youtu.be/{meta['video_id']}?t={int(t)}"
    return None


def assign(segments: list[Segment], starts: list[float], end: float) -> list[str]:
    """The words spoken while each frame is on screen (by the middle of each segment)."""
    bounds = starts + [end + 1]
    said = [[] for _ in starts]
    for seg in segments:
        mid = (seg.start + seg.end) / 2
        for i in range(len(starts)):
            if bounds[i] <= mid < bounds[i + 1] or (i == 0 and mid < bounds[0]):
                said[i].append(seg.text)
                break
    return [" ".join(words) for words in said]


def render(meta: dict, frame_names: list[str], starts: list[float], said: list[str], sheets: list[str],
           duration: float, how: str) -> str:
    lines = [f"# {meta.get('title') or meta.get('id')}", ""]
    facts = [
        ("source", meta.get("url") or meta.get("file")),
        ("channel", meta.get("channel")),
        ("published", meta.get("upload_date")),
        ("duration", clock(duration)),
        ("views", meta.get("views")),
        ("transcript", how),
        ("overview", ", ".join(sheets)),
    ]
    lines += [f"- {k}: {v}" for k, v in facts if v not in (None, "")]
    if meta.get("description"):
        lines += ["", "> " + meta["description"][:600].replace("\n", "\n> ")]
    chapters = meta.get("chapters") or []
    next_chapter = 0
    for i, name in enumerate(frame_names):
        while next_chapter < len(chapters) and chapters[next_chapter]["start_time"] <= starts[i] + 0.01:
            lines += ["", f"## Chapter: {chapters[next_chapter]['title']} ({clock(chapters[next_chapter]['start_time'])})"]
            next_chapter += 1
        link = link_at(meta, starts[i])
        heading = f"### {clock(starts[i])}" + (f" — [open]({link})" if link else "")
        lines += ["", heading, f"![{name}](frames/{name})", "", said[i] or "_(no speech)_"]
    return "\n".join(lines) + "\n"


def build(item_dir: Path, meta: dict, transcriber: Transcriber, keep_media: bool = False) -> dict:
    """Write frames/, sheet-N.jpg, transcript.txt and notes.md into `item_dir`. Returns a summary."""
    media = item_dir / "media"
    video = Path(meta["video_file"])
    audio = Path(meta.get("audio_file") or video)
    frames, duration = key_frames(video)
    for old in ("frames",):
        shutil.rmtree(item_dir / old, ignore_errors=True)
    for old in item_dir.glob("sheet-*.jpg"):
        old.unlink()
    names = save_frames(frames, item_dir / "frames")
    sheets = contact_sheets(frames, item_dir)
    subtitles = [Path(p) for p in meta.get("subtitle_files") or []]
    if subtitles:
        segments = parse_vtt(subtitles[0].read_text(encoding="utf-8", errors="replace"))
        how = f"creator subtitles ({subtitles[0].name})"
    else:
        segments, how = transcriber.transcribe(audio)
    (item_dir / "transcript.txt").write_text(
        "\n".join(f"[{clock(s.start)}-{clock(s.end)}] {s.text}" for s in segments), encoding="utf-8")
    starts = [f.t for f in frames]
    said = assign(segments, starts, duration)
    (item_dir / "notes.md").write_text(render(meta, names, starts, said, sheets, duration, how), encoding="utf-8")
    if not keep_media and media.exists():
        shutil.rmtree(media, ignore_errors=True)
    summary = {"frames": len(frames), "sheets": len(sheets), "segments": len(segments),
               "duration": round(duration, 1), "transcript": how}
    (item_dir / "meta.json").write_text(json.dumps({**meta, "notes": summary}, indent=1, ensure_ascii=False),
                                        encoding="utf-8")
    return summary
