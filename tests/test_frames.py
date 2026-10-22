import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from viddoc.frames import clock, frame_budget, key_frames
from viddoc.notes import assign
from viddoc.transcript import Segment


def write_video(path: Path, scenes: list[tuple[float, tuple[int, int, int]]], duration: float, fps: int = 10,
                fade_at: float | None = None, black_until: float = 0.0):
    """A shape on a light canvas whose colour switches at the given times, a tiny ticking counter
    (well under 1 %), optionally black at the start and a 1 s cross-fade into the scene at `fade_at`."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))

    def scene(colour):
        img = np.full((240, 320, 3), 230, np.uint8)
        cv2.rectangle(img, (80, 60), (240, 180), colour, -1)
        return img

    for i in range(int(duration * fps)):
        t = i / fps
        starts = [s for s, _ in scenes if t >= s]
        img = scene(scenes[len(starts) - 1][1])
        if fade_at is not None and fade_at <= t < fade_at + 1:
            before = scene(scenes[len(starts) - 2][1])
            img = cv2.addWeighted(before, 1 - (t - fade_at), img, t - fade_at, 0)
        if t < black_until:
            img = np.zeros_like(img)
        cv2.putText(img, str(i % 10), (300, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (128, 128, 128), 1)
        writer.write(img)
    writer.release()


class KeyFrames(unittest.TestCase):
    def test_one_frame_per_scene_and_no_static_repeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.mp4"
            write_video(path, [(0, (40, 40, 40)), (5, (200, 120, 30)), (25, (30, 160, 60))], duration=40)
            frames, duration = key_frames(path)
        self.assertAlmostEqual(duration, 40, delta=0.2)
        self.assertEqual([round(f.t) for f in frames], [0, 5, 25])  # 20 s static scene: still one frame

    def test_black_start_is_skipped_and_a_fade_gives_its_end_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fade.mp4"
            write_video(path, [(0, (40, 40, 200)), (10, (40, 200, 40))], duration=20, black_until=2, fade_at=10)
            frames, _ = key_frames(path)
        times = [f.t for f in frames]
        self.assertEqual(len(times), 2, times)
        self.assertAlmostEqual(times[0], 2.0, delta=0.6)   # first non-black frame
        self.assertGreaterEqual(times[1], 10.9)            # after the fade finished, not in the middle

    def test_budget_scales_with_length(self):
        self.assertEqual(frame_budget(60), 30)
        self.assertEqual(frame_budget(600), 120)
        self.assertEqual(frame_budget(7200), 150)

    def test_clock(self):
        self.assertEqual(clock(72.4), "1:12")
        self.assertEqual(clock(3725), "1:02:05")


class Assign(unittest.TestCase):
    def test_words_go_to_the_frame_on_screen(self):
        segments = [Segment(0.5, 2.0, "intro"), Segment(5.5, 7.0, "tip one"), Segment(26, 30, "tip two")]
        self.assertEqual(assign(segments, [0, 5, 25], 40), ["intro", "tip one", "tip two"])


if __name__ == "__main__":
    unittest.main()
