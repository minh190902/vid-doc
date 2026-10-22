"""Key frames: keep a frame when the picture has changed, never keep the same picture twice."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Frame:
    t: float
    image: np.ndarray
    change: float  # % of the thumbnail that moved since the previous kept frame


def changed_percent(a: np.ndarray, b: np.ndarray) -> float:
    """Share (%) of a 64x64 colour thumbnail where some channel moved by more than 25 levels.
    Colour, not grey: two scenes of equal brightness but different hue must count as a change."""
    return float(np.mean(cv2.absdiff(a, b).max(axis=2) > 25) * 100)


def thumb(image: np.ndarray) -> np.ndarray:
    return cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)


def frame_budget(duration: float) -> int:
    """About one frame per 6 s of video, between 30 and 150."""
    return int(min(150, max(30, 20 + duration / 6)))


def is_blank(small: np.ndarray) -> bool:
    """A black, white or single-colour frame (fades, title cards before they draw)."""
    return float(small.std()) < 4.0


def key_frames(path: Path, every: float = 0.5, change: float = 6.0, big: float = 20.0, spacing: float = 1.5,
               stable: float = 2.0, max_gap: float = 8.0, min_change: float = 1.0, settle: float = 3.0,
               max_frames: int | None = None, height: int = 720) -> tuple[list[Frame], float]:
    """Pick the frames that show a new step, sampled every `every` s.

    A sample is kept when, compared with the last kept frame, more than `change` % of the picture changed
    and at least `spacing` s passed (or more than `big` % changed: a cut), or `max_gap` s passed and at
    least `min_change` % changed (slow drawing). It is kept only once the picture has settled: it differs
    from the next sample by less than `stable` %, so fades and pans give their end frame, not their
    middle; after `settle` s of continuous motion it is kept anyway. Blank frames are never kept."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps * every))
    kept: list[Frame] = []
    last_thumb, last_t = None, -1e9
    pending = None  # (t, image, thumb) of the previous sample, judged when the next one arrives
    moving_since = None

    def judge(t, image, small, settled):
        nonlocal last_thumb, last_t, moving_since
        if is_blank(small):
            return
        moved = 100.0 if last_thumb is None else changed_percent(small, last_thumb)
        wanted = (moved > change and (t - last_t >= spacing or moved > big)) or \
                 (t - last_t >= max_gap and moved >= min_change)
        if not wanted:
            moving_since = None
            return
        if not settled:
            moving_since = t if moving_since is None else moving_since
            if t - moving_since < settle:
                return
        h, w = image.shape[:2]
        if h > height:
            image = cv2.resize(image, (round(w * height / h), height), interpolation=cv2.INTER_AREA)
        kept.append(Frame(t, image, moved))
        last_thumb, last_t, moving_since = small, t, None

    index = 0
    while cap.grab():
        if index % step == 0:
            ok, image = cap.retrieve()
            if not ok:
                break
            small = thumb(image)
            if pending is not None:
                judge(*pending, settled=changed_percent(pending[2], small) < stable)
            pending = (index / fps, image, small)
        index += 1
    cap.release()
    if pending is not None:
        judge(*pending, settled=True)
    duration = index / fps
    budget = max_frames or frame_budget(duration)
    if len(kept) > budget:
        first, rest = kept[0], sorted(kept[1:], key=lambda f: -f.change)[: budget - 1]
        kept = [first] + sorted(rest, key=lambda f: f.t)
    return kept, duration


def clock(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}" if t >= 3600 else f"{int(t // 60)}:{int(t % 60):02d}"


def save_frames(frames: list[Frame], out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    names = []
    for i, frame in enumerate(frames, 1):
        name = f"{i:03d}_t{frame.t:07.1f}.jpg"
        cv2.imwrite(str(out / name), frame.image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        names.append(name)
    return names


def contact_sheets(frames: list[Frame], out: Path, cols: int = 4, per_sheet: int = 12, cell: int = 360) -> list[str]:
    """Grids of `per_sheet` frames, each labelled with its time; vertical clips get narrower cells."""
    names = []
    for start in range(0, len(frames), per_sheet):
        tiles = []
        for frame in frames[start:start + per_sheet]:
            h, w = frame.image.shape[:2]
            width = cell if w >= h else cell * 2 // 3
            tile = cv2.resize(frame.image, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)
            label = clock(frame.t)
            cv2.rectangle(tile, (0, 0), (14 + 12 * len(label), 26), (0, 0, 0), -1)
            cv2.putText(tile, label, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(tile)
        tw = max(t.shape[1] for t in tiles)
        th = max(t.shape[0] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, tw - t.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
                 for t in tiles]
        while len(tiles) % cols:
            tiles.append(np.full_like(tiles[0], 255))
        rows = [cv2.hconcat(tiles[r:r + cols]) for r in range(0, len(tiles), cols)]
        name = f"sheet-{start // per_sheet + 1}.jpg"
        cv2.imwrite(str(out / name), cv2.vconcat(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
        names.append(name)
    return names
