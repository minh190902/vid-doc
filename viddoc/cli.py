"""vid-doc command line. Every command here is deterministic; judgement (which clips to keep, what the
tips are) belongs to the agent driving it — see skill/SKILL.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from viddoc import youtube
from viddoc.config import library_dir, load_config, save_config
from viddoc.library import Library, slug

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
REPO = Path(__file__).resolve().parent.parent


def lib() -> Library:
    library = Library(library_dir())
    library.ensure()
    return library


def fmt_duration(seconds) -> str:
    if not isinstance(seconds, (int, float)):
        return "?"
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def table(entries: list[dict]) -> None:
    for e in entries:
        views = e.get("views")
        views = f"{views:,}" if isinstance(views, int) else "?"
        print(f"{e['id']:<16} {fmt_duration(e.get('duration')):>6} {views:>11}  {(e.get('channel') or '?')[:22]:<22}  "
              f"{(e.get('title') or '')[:80]}")


# setup ----------------------------------------------------------------------------------------
def link_skill() -> None:
    skills = Path.home() / ".claude" / "skills"
    link, target = skills / "vid-doc", REPO / "skill"
    skills.mkdir(parents=True, exist_ok=True)
    if link.exists():
        if link.resolve() == target.resolve():
            print(f"skill already linked: {link}")
        else:
            print(f"skill NOT linked: {link} exists and points elsewhere ({link.resolve()}); remove it to relink")
        return
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)
    print(f"skill linked: {link} -> {target}")


def cmd_setup(args) -> int:
    config = load_config()
    if args.library:
        config["library"] = str(Path(args.library).resolve())
        save_config(config)
    library = lib()
    print(f"library: {library.root}")
    if not args.no_skill_link:
        link_skill()
    print("tools:", youtube.tool("yt-dlp"), youtube.tool("deno"), sep="\n  ")
    return 0


def cmd_update(args) -> int:
    return subprocess.call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]", "deno"])


# discovery ------------------------------------------------------------------------------------
def report_found(library: Library, found: list[dict]) -> int:
    fresh = library.add_found(found)
    print(f"{len(found)} results, {len(fresh)} new (the rest are already in the library)")
    table(fresh)
    return 0


def cmd_find(args) -> int:
    library = lib()
    found: list[dict] = []
    try:
        if args.what == "search":
            lengths = {"both": ("short", "medium"), "short": ("short",), "medium": ("medium",), "any": ("any",)}
            found = youtube.search(" ".join(args.query), args.max, lengths[args.length])
        else:
            channels = args.channel or library.channels()
            for channel in channels:
                try:
                    found += youtube.channel_latest(channel, args.per_tab)
                except RuntimeError as error:
                    print(f"! {channel}: {str(error).splitlines()[-1][:160]}")
    except youtube.Blocked as error:
        print(f"BLOCKED by YouTube, stopping: {error}")
        return 2
    return report_found(library, found)


def cmd_pick(args) -> int:
    missing = lib().set_status(args.ids, "picked", error=None)
    print(f"picked {len(args.ids) - len(missing)}" + (f"; unknown: {' '.join(missing)}" if missing else ""))
    return 1 if missing else 0


def cmd_reject(args) -> int:
    missing = lib().set_status(args.ids, "rejected", reason=args.reason)
    print(f"rejected {len(args.ids) - len(missing)}" + (f"; unknown: {' '.join(missing)}" if missing else ""))
    return 1 if missing else 0


def cmd_done(args) -> int:
    missing = lib().set_status(args.ids, "digested", digest=args.digest)
    print(f"digested {len(args.ids) - len(missing)}" + (f"; unknown: {' '.join(missing)}" if missing else ""))
    return 1 if missing else 0


# fetching -------------------------------------------------------------------------------------
def cmd_fetch(args) -> int:
    library = lib()
    queue = sorted(library.with_status("picked"), key=lambda e: e["updated"])[: args.limit]
    if not queue:
        print("nothing picked; use `pick <id>...` first")
        return 0
    forbidden_in_a_row = 0
    for entry in queue:
        item_id = entry["id"]
        try:
            info = youtube.metadata(entry["url"])
            duration = info.get("duration") or 0
            if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
                library.set_status([item_id], "rejected", reason="live stream")
                print(f"- {item_id}: live, rejected")
                continue
            if duration > args.max_duration:
                library.set_status([item_id], "rejected", reason=f"too long ({fmt_duration(duration)})")
                print(f"- {item_id}: {fmt_duration(duration)} is over --max-duration, rejected")
                continue
            item_dir = library.item_dir(item_id)
            files = youtube.download(entry["url"], item_dir / "media")
        except youtube.Blocked as error:
            print(f"BLOCKED by YouTube at {item_id}, stopping the batch (it stays picked): {error}")
            return 2
        except youtube.Forbidden as error:
            forbidden_in_a_row += 1
            library.set_status([item_id], "failed", error=f"HTTP 403 on its media (needs a PO token?): {error}")
            print(f"x {item_id}: HTTP 403 on its media, skipped")
            if forbidden_in_a_row >= 3:
                print("BLOCKED: three clips in a row got HTTP 403, stopping the batch")
                return 2
            continue
        except Exception as error:  # one bad clip must not stop the batch
            library.set_status([item_id], "failed", error=str(error)[-300:])
            print(f"x {item_id}: {str(error)[-160:]}")
            continue
        meta = {
            "id": item_id, "source": "youtube", "url": entry["url"], "video_id": info.get("id"),
            "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
            "upload_date": info.get("upload_date"), "duration": duration, "views": info.get("view_count"),
            "description": info.get("description") or "", "tags": info.get("tags") or [],
            "chapters": [{"start_time": c["start_time"], "end_time": c["end_time"], "title": c["title"]}
                         for c in info.get("chapters") or []],
            "origin": entry.get("origin"),
            "video_file": str(files["video"]), "audio_file": str(files["audio"]) if files["audio"] else None,
            "subtitle_files": [str(p) for p in files["subtitles"]],
        }
        (item_dir / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
        forbidden_in_a_row = 0
        library.set_status([item_id], "fetched", title=meta["title"], channel=meta["channel"], duration=duration,
                           views=meta["views"], error=None)
        print(f"+ {item_id}: {fmt_duration(duration)} {meta['title'][:70]}"
              + (f" (creator subtitles: {len(files['subtitles'])})" if files["subtitles"] else ""))
    return 0


def cmd_inbox(args) -> int:
    library = lib()
    added = 0
    for video in sorted(p for p in library.inbox.iterdir() if p.suffix.lower() in VIDEO_EXT):
        digest = hashlib.sha1(f"{video.name}:{video.stat().st_size}".encode()).hexdigest()[:8]
        item_id = f"inbox-{slug(video.stem, 32)}-{digest}"
        if item_id in library.load():
            continue
        media = library.item_dir(item_id) / "media"
        media.mkdir(parents=True, exist_ok=True)
        moved = Path(shutil.move(str(video), str(media / video.name)))
        meta = {"id": item_id, "source": "inbox", "title": video.stem, "file": video.name,
                "video_file": str(moved), "audio_file": None, "subtitle_files": [], "keep_media": True}
        (library.item_dir(item_id) / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False),
                                                              encoding="utf-8")
        library.add_found([{"id": item_id, "source": "inbox", "title": video.stem}])
        library.set_status([item_id], "fetched")
        print(f"+ {item_id}")
        added += 1
    print(f"{added} new inbox video(s); run `notes` next")
    return 0


# notes ----------------------------------------------------------------------------------------
def cmd_notes(args) -> int:
    from viddoc.notes import build
    from viddoc.transcript import Transcriber

    library = lib()
    queue = library.with_status("fetched")
    if args.ids:
        queue = [e for e in library.load().values() if e["id"] in args.ids]
    if not queue:
        print("nothing fetched; use `fetch` or `inbox` first")
        return 0
    transcriber = Transcriber(fast=args.fast)
    for entry in queue:
        item_dir = library.item_dir(entry["id"])
        try:
            meta = json.loads((item_dir / "meta.json").read_text(encoding="utf-8"))
            if not Path(meta["video_file"]).exists():
                print(f"- {entry['id']}: video was deleted after its notes; `pick` and `fetch` it again to redo")
                continue
            summary = build(item_dir, meta, transcriber, keep_media=args.keep_media or meta.get("keep_media", False))
        except Exception as error:
            library.set_status([entry["id"]], "failed", error=f"notes: {str(error)[-300:]}")
            print(f"x {entry['id']}: {str(error)[-160:]}")
            continue
        library.set_status([entry["id"]], "noted", notes=str(item_dir / "notes.md"), error=None)
        print(f"+ {entry['id']}: {summary['frames']} frames, {summary['segments']} speech segments, {summary['transcript']}")
    return 0


# reading --------------------------------------------------------------------------------------
def cmd_list(args) -> int:
    library = lib()
    entries = [e for e in library.load().values() if not args.status or e.get("status") in args.status]
    entries.sort(key=lambda e: e.get("updated", ""))
    for e in entries:
        extra = e.get("reason") or e.get("error") or e.get("notes") or ""
        print(f"{e.get('status', '?'):<9} ", end="")
        table([e])
        if extra:
            print(f"{'':<10}{extra}")
    print(f"{len(entries)} item(s) in {library.root}")
    return 0


def cmd_status(args) -> int:
    library = lib()
    counts: dict[str, int] = {}
    for e in library.load().values():
        counts[e.get("status", "?")] = counts.get(e.get("status", "?"), 0) + 1
    inbox = [p.name for p in library.inbox.iterdir() if p.suffix.lower() in VIDEO_EXT]
    print(f"library: {library.root}")
    print("  " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) if counts else "  empty")
    print(f"  inbox waiting: {len(inbox)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(prog="vid-doc", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("setup", help="create the library, link the Claude Code skill")
    p.add_argument("--library", help="library folder (remembered in the config)")
    p.add_argument("--no-skill-link", action="store_true")
    p.set_defaults(func=cmd_setup)
    sub.add_parser("update", help="upgrade yt-dlp and deno").set_defaults(func=cmd_update)

    p = sub.add_parser("find", help="find candidate clips (records them as 'found')")
    fsub = p.add_subparsers(dest="what", required=True)
    s = fsub.add_parser("search")
    s.add_argument("query", nargs="+")
    s.add_argument("--max", type=int, default=15, help="results per length filter")
    s.add_argument("--length", choices=("both", "short", "medium", "any"), default="both",
                   help="short < 4 min, medium 4-20 min; both (default) runs the two")
    s.set_defaults(func=cmd_find)
    c = fsub.add_parser("channels")
    c.add_argument("--channel", action="append", help="instead of channels.txt (repeatable)")
    c.add_argument("--per-tab", type=int, default=5, help="newest N of each channel's Shorts and Videos tabs")
    c.set_defaults(func=cmd_find)

    p = sub.add_parser("pick", help="mark found clips to fetch")
    p.add_argument("ids", nargs="+")
    p.set_defaults(func=cmd_pick)
    p = sub.add_parser("reject", help="mark clips not worth fetching")
    p.add_argument("ids", nargs="+")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_reject)
    p = sub.add_parser("fetch", help="download picked clips (video <=480p + audio, creator subtitles)")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--max-duration", type=int, default=1200, help="seconds; longer clips are rejected")
    p.set_defaults(func=cmd_fetch)
    sub.add_parser("inbox", help="take videos dropped into inbox/").set_defaults(func=cmd_inbox)
    p = sub.add_parser("notes", help="frames + transcript + notes.md for fetched clips")
    p.add_argument("ids", nargs="*", help="re-run these instead of every fetched clip")
    p.add_argument("--fast", action="store_true", help="distil-large-v3 for English (misses jargon)")
    p.add_argument("--keep-media", action="store_true", help="do not delete the downloaded video")
    p.set_defaults(func=cmd_notes)
    p = sub.add_parser("done", help="mark clips as digested")
    p.add_argument("ids", nargs="+")
    p.add_argument("--digest", help="the digest file that covers them")
    p.set_defaults(func=cmd_done)
    p = sub.add_parser("list", help="list items")
    p.add_argument("--status", action="append", help="filter (repeatable)")
    p.set_defaults(func=cmd_list)
    sub.add_parser("status", help="counts by status").set_defaults(func=cmd_status)

    args = ap.parse_args(argv)
    return args.func(args)
