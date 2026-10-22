# vid-doc

Turn tutorial videos — picture **and** voice — into notes an AI agent can read: key frames, a timed
transcript, and a `notes.md` that pairs each frame with what is said while it is on screen. Built for
studying short tips about making game assets (pixel art, sprites, tiles, animation), but nothing in the
tool is specific to that.

It runs on your machine and costs nothing: [yt-dlp](https://github.com/yt-dlp/yt-dlp) finds and
downloads clips, OpenCV picks frames, [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
transcribes on the CPU. It ships as a [Claude Code skill](https://code.claude.com/docs/en/skills): the
tool does the deterministic work, the agent decides which clips are worth reading and writes the digest.

## How it works

```
find (search / channels) ─▶ agent shortlists ─▶ fetch ─▶ notes ─▶ agent writes digest + tips.md
inbox (videos you drop in, e.g. from Instagram) ───────▶ notes ─┘
```

| Step | Who | What |
|---|---|---|
| `find search <words>` / `find channels` | tool | YouTube search with a duration filter (< 4 min and 4–20 min), or the newest Shorts and Videos of the channels in `channels.txt`; skips clips already seen |
| shortlist | agent | `pick` the clips that teach something, `reject` the rest with a reason |
| `fetch` | tool | video with its short side ≤ 480 px plus audio (separate files, no ffmpeg needed), creator-uploaded subtitles; pauses between requests; stops on any block |
| `inbox` | tool | takes the videos you dropped into `inbox/` |
| `notes` | tool | key frames (a static scene gives one frame), contact sheets, transcript, `notes.md` with chapters and timestamp links; deletes the downloaded video afterwards |
| digest | agent | tips with evidence (clip, timestamp, frame), merged into `tips.md` |

Transcripts come from the creator's own subtitles when there are any, otherwise from Whisper
`large-v3`. YouTube's automatic captions are not used: on a pixel-art clip they heard "dithering" as
"deterring" every time, and so did `distil-large-v3`; `large-v3` got it right. Vietnamese speech uses
PhoWhisper. See [docs/DESIGN.md](docs/DESIGN.md) for the measurements behind each choice.

## Install

Needs Python 3.10+ and git. Windows, macOS and Linux.

```
git clone https://github.com/minh190902/vid-doc.git
python vid-doc/skill/run.py setup --library <folder for your notes>
```

The first run creates the tool's own virtual environment (`%LOCALAPPDATA%\vid-doc\venv` on Windows,
`~/.local/share/vid-doc/venv` elsewhere) and installs yt-dlp, Deno (yt-dlp needs a JavaScript runtime
for YouTube), faster-whisper and OpenCV into it. `setup` also links `skill/` into
`~/.claude/skills/vid-doc` so Claude Code finds it in every project. Whisper models (~3 GB for
`large-v3`) download on first use into the Hugging Face cache.

## Use

In Claude Code:

```
/vid-doc search pixel art dithering
/vid-doc channels
/vid-doc inbox
```

Or by hand (`python skill/run.py <command>`):

```
status                         counts by status, inbox waiting
find search <words> [--length both|short|medium|any] [--max 15]
find channels [--per-tab 5] [--channel @handle]
pick <id>...   reject <id>... --reason "off-topic"
fetch [--limit 20] [--max-duration 1200]
inbox
notes [--fast] [--keep-media] [<id>...]
list [--status noted]
done <id>... --digest <file>
update                         upgrade yt-dlp and deno (YouTube changes often)
```

## Library layout

```
inbox/            drop videos here
items/<id>/       meta.json, frames/, sheet-N.jpg, transcript.txt, notes.md
index.json        every clip seen and its status: found, picked, rejected, fetched, noted, digested, failed
channels.txt      channels to watch, one @handle per line
digests/          one digest per run, written by the agent
tips.md           the tip catalogue across all runs
```

## Time

On a laptop CPU: about 2 minutes to load `large-v3` once per batch, then about 1.1× the length of each
clip. Ten one-minute tips take about 15 minutes, unattended.

## Responsible use

YouTube's Terms of Service do not allow downloading content without permission. This tool is meant for
personal study: it fetches small batches with pauses, never uses your account or cookies, stops at the
first sign of a block, and deletes each video once its notes are written. Do not publish the frames or
transcripts it produces; link to the original creators instead. Instagram has no practical search API
and forbids automated access, so clips from there go through `inbox/` by hand.

## License

MIT — see [LICENSE](LICENSE).
