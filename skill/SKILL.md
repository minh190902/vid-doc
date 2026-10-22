---
name: vid-doc
description: >-
  Find and study tutorial videos about making game assets (pixel art, sprites, tiles, animation, palettes,
  AI-assisted asset workflows): search YouTube or watched channels, or take clips dropped into the inbox
  (e.g. from Instagram), turn picture + voice into key frames and a timed transcript, then write a digest of
  the tips with links and timestamps. Use when the user asks to research video tips, "xem inbox",
  "tìm clip hướng dẫn", "tìm tip làm asset", "tổng hợp tip từ video", or runs /vid-doc.
argument-hint: "search <topic> | channels | inbox | digest | status"
allowed-tools: Bash(python *) Read Write Edit Glob Grep
---

# vid-doc

Run the tool through its launcher (it creates its own venv on first use):

```
python "${CLAUDE_SKILL_DIR}/run.py" <command>
```

Commands: `status`, `find search <words> [--length both|short|medium|any] [--max N]`,
`find channels [--per-tab N]`, `pick <id>...`, `reject <id>... --reason "..."`, `fetch [--limit N]`,
`inbox`, `notes [--fast] [--keep-media]`, `list [--status S]`, `done <id>... --digest <file>`, `update`.
The library path is printed by `status`; it holds `items/<id>/notes.md`, `digests/`, `tips.md`,
`channels.txt`.

Request: `$ARGUMENTS`

## Workflows

- **search <topic>**: `find search <topic>` → shortlist → `fetch` → `notes` → digest.
- **channels**: `find channels` → shortlist → `fetch` → `notes` → digest.
- **inbox**: `inbox` → `notes` → digest.
- **digest**: digest every item with status `noted` (`list --status noted`).
- **status** (or nothing): `status`, then say what is waiting.

If the request is plain words ("tìm tip shading"), treat it as `search` with those words in English
(YouTube results are mostly English); say which query you used.

## Shortlisting (your judgement)

Read the candidate table. **Pick** clips that teach a technique for making game assets: pixel art,
sprites, tiles, animation, palettes, lighting, readability, asset workflows, using AI for assets.
**Reject** with a short reason: off-topic (crafts, Minecraft builds, speed-paint showcases with no
teaching), pure promotion, duplicates of a clip already picked, live streams. Prefer short tips
(< 4 min), but take a long tutorial (4–20 min) when its title promises several concrete techniques.
Pick at most 10 per run unless the user asked for more. A good clip you do not take this run stays
`found` (the backlog; `list --status found` shows it) — reject only what is not worth reading at all,
because a rejected clip is never offered again. Run `pick` and `reject` once each with all ids.

## Fetch and notes

- `fetch` downloads at most 20 clips with pauses. If it prints **BLOCKED**, stop and tell the user. Never
  pass cookies or a Google account, never use proxies, never retry in a loop.
- `notes` is slow on CPU: about 2 minutes to load the speech model, then about 1.1× the clip length.
  For more than ~3 minutes of video, run it in the background and tell the user it is running.
- Videos are deleted after notes (inbox videos are kept). Only frames, text and links remain.

## Reading an item

1. Open `sheet-1.jpg` (and later sheets for long clips) to see the steps.
2. Read `notes.md`: each frame with the words said while it shows, chapters for long videos, and an
   `[open]` link to that moment.
3. Open single files in `frames/` only when a detail matters (a palette, a pixel cluster).

The transcript can mishear words; trust what the frames show when they disagree, and say so.

## Writing the digest

Use [summary-template.md](summary-template.md). Write `digests/<YYYY-MM-DD>-<topic-slug>.md` in the
library, then merge each tip into `tips.md`: if a tip is already there, add the new source under it
instead of a second entry. Then run `done <ids> --digest <that file>`.

When the current project has its own art rules or pipeline docs (for example Asset Foundry's
`docs/`), fill the "Project" column by checking them: **has** (already does it), **missing**,
**conflicts** (we do the opposite). Otherwise leave that column out.

Reply to the user with the 3–5 most useful tips and the digest path, in the user's language.

## Rules

- Personal research: never publish frames or transcripts; quote at most a sentence; always link the source.
- Do not edit the tool's code to get past an error; report the error.
