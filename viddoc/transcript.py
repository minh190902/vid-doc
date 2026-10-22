"""Speech to timed text: creator-uploaded subtitles when present, else Whisper on this machine.

Measured 2026-10-16 on an 84 s pixel-art clip: YouTube auto captions and distil-large-v3 heard
"dithering" as "deterring"; large-v3 got it right 7/7 at about 1.1x real time on CPU. So large-v3 is
the default; `fast` uses distil-large-v3 for English only. Vietnamese uses PhoWhisper-medium.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

GLOSSARY = {
    "en": ("Pixel art and game asset tutorial. Terms: dithering, anti-aliasing, hue shifting, outline, selout, "
           "jaggies, sub-pixel, palette, ramp, sprite, sprite sheet, tileset, autotile, Aseprite, Photoshop."),
}
PHOWHISPER = ("quocphu/PhoWhisper-ct2-FasterWhisper", "PhoWhisper-medium-ct2-fasterWhisper")


@dataclass
class Segment:
    start: float
    end: float
    text: str


_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{3})|(\d{2}):(\d{2})[.,](\d{3})")


def _seconds(stamp: str) -> float:
    m = _TIME.fullmatch(stamp.strip())
    if not m:
        raise ValueError(stamp)
    if m.group(1):
        h, mi, s, ms = (int(m.group(i)) for i in range(1, 5))
    else:
        h, (mi, s, ms) = 0, (int(m.group(i)) for i in range(5, 8))
    return h * 3600 + mi * 60 + s + ms / 1000


def parse_vtt(text: str) -> list[Segment]:
    """WebVTT cues as segments. Inline timing tags are dropped and the rolling repeats of
    auto-style captions (each cue repeating the previous line) are removed."""
    segments: list[Segment] = []
    emitted: list[str] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [l for l in block.strip().split("\n") if l.strip()]
        timing = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if timing is None:
            continue
        start, end = (part.split()[0] for part in lines[timing].split("-->"))
        body = [" ".join(html.unescape(re.sub(r"<[^>]+>", "", l)).split()) for l in lines[timing + 1:]]
        new = [l for l in body if l and l not in emitted[-3:]]
        if not new:
            continue
        emitted += new
        segments.append(Segment(_seconds(start), _seconds(end), " ".join(new)))
    return segments


def has_audio(path: Path) -> bool:
    import av

    with av.open(str(path)) as container:
        return bool(container.streams.audio)


class Transcriber:
    """Loads each Whisper model once and reuses it across a batch."""

    def __init__(self, fast: bool = False):
        self.fast = fast
        self._models: dict[str, object] = {}

    def _model(self, name: str):
        if name not in self._models:
            from faster_whisper import WhisperModel

            path = name
            if name == "phowhisper":
                from huggingface_hub import snapshot_download

                repo, sub = PHOWHISPER
                path = str(Path(snapshot_download(repo, allow_patterns=[f"{sub}/*"])) / sub)
            self._models[name] = WhisperModel(path, device="cpu", compute_type="int8")
        return self._models[name]

    def detect(self, audio: Path) -> str | None:
        _, info = self._model("base").transcribe(str(audio), beam_size=1, vad_filter=True)
        return info.language if info.language_probability >= 0.5 else None

    def transcribe(self, audio: Path, language: str | None = None) -> tuple[list[Segment], str]:
        """Returns segments and a note on how they were made. A file without an audio track and
        music-only audio give no segments; any other failure raises, so the item is marked failed
        instead of passing as a clip with no speech."""
        if not has_audio(audio):
            return [], "no audio track"
        language = language or self.detect(audio)
        if language == "vi":
            name = "phowhisper"
        elif language == "en" and self.fast:
            name = "distil-large-v3"
        else:
            name = "large-v3"
        # condition_on_previous_text=False: with it on, large-v3 looped on an 8:55 tutorial
        # ("less and less and less ..." x20) and repeated a later sentence at the start.
        segments, info = self._model(name).transcribe(
            str(audio), language=language, beam_size=5, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=GLOSSARY.get(language or ""))
        result = [Segment(s.start, s.end, s.text.strip()) for s in segments if s.text.strip()]
        return result, f"whisper {name}, language {info.language}"
