import tempfile
import unittest
from pathlib import Path

from viddoc.library import Library, slug


class LibraryIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Library(Path(self.tmp.name))
        self.lib.ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ensure_creates_layout_once(self):
        for name in ("inbox", "items", "digests", "channels.txt", "tips.md", "index.json"):
            self.assertTrue((self.lib.root / name).exists(), name)
        (self.lib.root / "tips.md").write_text("mine", encoding="utf-8")
        self.lib.ensure()
        self.assertEqual((self.lib.root / "tips.md").read_text(encoding="utf-8"), "mine")

    def test_found_is_deduplicated_against_every_status(self):
        first = self.lib.add_found([{"id": "yt-a"}, {"id": "yt-b"}])
        self.assertEqual([e["id"] for e in first], ["yt-a", "yt-b"])
        self.lib.set_status(["yt-a"], "rejected", reason="off-topic")
        again = self.lib.add_found([{"id": "yt-a"}, {"id": "yt-c"}])
        self.assertEqual([e["id"] for e in again], ["yt-c"])
        self.assertEqual(self.lib.load()["yt-a"]["status"], "rejected")

    def test_set_status_reports_unknown_ids_and_rejects_unknown_status(self):
        self.lib.add_found([{"id": "yt-a"}])
        self.assertEqual(self.lib.set_status(["yt-a", "yt-zz"], "picked"), ["yt-zz"])
        self.assertEqual([e["id"] for e in self.lib.with_status("picked")], ["yt-a"])
        with self.assertRaises(ValueError):
            self.lib.set_status(["yt-a"], "maybe")

    def test_channels_skip_comments(self):
        self.assertIn("@MortMort", self.lib.channels())
        self.assertFalse(any(c.startswith("#") for c in self.lib.channels()))

    def test_slug(self):
        self.assertEqual(slug("Pixel Art: Shading 101!"), "pixel-art-shading-101")
        self.assertEqual(slug("!!!"), "item")


if __name__ == "__main__":
    unittest.main()
