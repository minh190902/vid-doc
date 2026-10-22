# Design

Why vid-doc is built the way it is. Every number here was measured on a Windows 11 laptop
(CPU only, home internet) on 2026-10-16 unless marked as coming from documentation.

## Goal

Study tutorial clips about making game assets without watching them one by one: find them, keep the
ones that teach something, and turn each into frames + timed words an AI agent can read, then into a
catalogue of tips with links back to the source.

## Split: tool versus agent

The tool (`viddoc/`) does only deterministic work — search, download, frames, transcript, files — so
it can be tested and run without an AI. The agent (`skill/SKILL.md`) does what needs judgement:
which clips are worth fetching and what the tips are. The library is plain files (`index.json`,
Markdown, JPEG) so any agent can read it.

## Measurements that decided the design

| Question | Measured | Decision |
|---|---|---|
| Does YouTube have the content? | 4 searches × 15 results: large pixel-art channels (MortMort, AdamCYounis, Brandon James Greer, Pixel Pete, Retronator…), several over 1 M views | YouTube is the searchable source |
| Plain search vs Shorts | Plain search returns mostly 5–15 min videos; the "under 4 min" filter (`sp=EgIYAQ%3D%3D`) returns short tips; "4–20 min" (`sp=EgIYAw%3D%3D`) returns tutorials | `find search` runs both filters by default |
| Hashtag Shorts pages | Mostly noise (e.g. Minecraft sand art under #pixelarttutorial) | Not used; channels and keyword search instead, then the agent shortlists |
| JS runtime | yt-dlp warns without one; Node 20.17 reported "unsupported" (needs ≥ 22); Deno 2.9.7 from `pip install deno` works with no warning | Deno is a pip dependency of the tool's venv |
| ffmpeg | Not installed; yt-dlp cannot merge, so video and audio arrive as separate files | Download them separately on purpose (`bv*,ba`); OpenCV reads the video, Whisper the audio |
| Vertical Shorts | `height<=480` gives a 270×480 Short | Limit the short side: `[height<=480][aspect_ratio>=1]/[width<=480][aspect_ratio<1]` → 480×854 |
| OpenCV and .webm (VP9) | Reads fine | — |
| Captions on jargon (84 s dithering tip) | YouTube auto captions: "deterring" ×7. distil-large-v3 (with a glossary prompt): "deterring" ×7, 22 s. large-v3: "dithering" ×7, 94 s + 134 s model load | large-v3 by default, loaded once per batch; creator subtitles when present; auto captions never |
| Frame selection on real clips | First rule (keep on > 4 % change, or every 4 s) caught the steps but kept fades, a black first frame, a blinking presenter: 23 frames for an 84 s tip, 56 for 222 s | Compare colour, not grey (an equal-brightness cut was missed); skip blank frames; keep a frame only once the picture settles (< 2 % change to the next sample); ≥ 1.5 s apart unless > 20 % changed; > 6 % to count as new, or ≥ 1 % after 8 s. Result: 10 and 32 frames, every one a distinct step |
| Download of an 8:55 tutorial | DASH (https) video: HTTP 403 mid-download, twice, 15 min apart, while metadata and the audio stream worked; the HLS (m3u8) video stream downloaded whole in 16 s | HLS H.264 first, then DASH. A 403 fails that clip only; three in a row stop the batch |
| Audio tracks | The same clip carries 20 AI-dubbed tracks next to the original | Audio filter `ba[format_note*=original]` first, never a dubbed track |
| PyAV | A fresh venv got PyAV 19, which removed an argument faster-whisper 1.2.1 passes; transcription failed and the failure was swallowed | Pin `av<19`; a transcription error now fails the clip instead of passing as "no speech"; the launcher reinstalls when `pyproject.toml` changes |
| Creator subtitles | Real VTT carries `&nbsp;` | Unescape HTML entities |

## Facts from documentation (October 2026)

- yt-dlp requires an external JS runtime for full YouTube support since 2025.11; `yt-dlp[default]`
  includes `yt-dlp-ejs`. Deno is the default runtime.
- YouTube removed upload-date sorting (2026-01) and yt-dlp removed `ytsearchdate` (2026-02).
- Flat search results carry no upload date, and Shorts entries carry no duration or channel, so
  `fetch` reads full metadata for each picked clip and applies `--max-duration` there.
- Guest sessions are throttled around 300 videos/hour; `-t sleep` adds pauses. Bot checks mostly hit
  datacenter IPs. A PO-token provider plugin exists if blocks appear; the tool does not escalate on
  its own and never uses account cookies.
- Auto-translated subtitle tracks are rate limited (HTTP 429); the tool fetches creator subtitles only.
- YouTube Data API v3 could replace scraping for search (search.list has its own 100 calls/day bucket
  since 2026-06-01, `videoDuration=short` < 4 min, no Shorts filter, an API key is enough) but cannot
  download captions of other people's videos. Not used yet.
- Instagram's hashtag API needs a Business account, App Review, 30 hashtags per 7 days and returns
  only the last 24 hours, so Instagram clips come through `inbox/`.
- YouTube's Terms of Service forbid downloading without permission; see "Responsible use" in the README.

## Known limits

- The new "Shorts" type filter code was not found; Shorts reach us through the duration filter and
  channel Shorts tabs.
- Only a handful of requests were made while measuring; behaviour at higher volume is unknown.
- PhoWhisper is wired for Vietnamese but was only checked to load and run, not on real speech.
- Frames show steps, not motion; animation timing tips can lose detail.
