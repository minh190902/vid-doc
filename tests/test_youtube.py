import unittest

from viddoc import youtube


class Urls(unittest.TestCase):
    def test_search_url_with_duration_filters(self):
        self.assertEqual(youtube.search_url("pixel art tips", "short"),
                         "https://www.youtube.com/results?search_query=pixel+art+tips&sp=EgIYAQ%253D%253D")
        self.assertTrue(youtube.search_url("x", "medium").endswith("&sp=EgIYAw%253D%253D"))
        self.assertNotIn("&sp=", youtube.search_url("x", "any"))

    def test_channel_url(self):
        self.assertEqual(youtube.channel_url("@MortMort", "shorts"), "https://www.youtube.com/@MortMort/shorts")
        self.assertEqual(youtube.channel_url("https://www.youtube.com/@X/", "videos"),
                         "https://www.youtube.com/@X/videos")


class FlatEntries(unittest.TestCase):
    def test_video_entry(self):
        entry = youtube.entry_from_flat({"_type": "url", "id": "abc", "title": "Tip", "duration": 84,
                                         "view_count": 10, "channel": "C"}, "search:q:short")
        self.assertEqual(entry["id"], "yt-abc")
        self.assertEqual(entry["url"], "https://www.youtube.com/watch?v=abc")
        self.assertEqual((entry["duration"], entry["views"], entry["channel"]), (84, 10, "C"))

    def test_shorts_lockup_without_duration_or_channel(self):
        entry = youtube.entry_from_flat({"id": "s1", "title": "Short", "view_count": 5}, "channel:@x:shorts")
        self.assertIsNone(entry["duration"])
        self.assertEqual(entry["channel"], "")

    def test_playlists_and_empty_ids_are_skipped(self):
        self.assertIsNone(youtube.entry_from_flat({"_type": "playlist", "id": "p"}, "x"))
        self.assertIsNone(youtube.entry_from_flat({"title": "no id"}, "x"))


class Blocks(unittest.TestCase):
    def test_session_refusals_block_the_batch(self):
        for text in ("ERROR: Sign in to confirm you're not a bot", "HTTP Error 429: Too Many Requests"):
            self.assertTrue(any(m in text for m in youtube.BLOCK_MARKERS), text)

    def test_a_403_is_per_clip_not_a_block(self):
        text = "ERROR: unable to download video data: HTTP Error 403: Forbidden"
        self.assertFalse(any(m in text for m in youtube.BLOCK_MARKERS))
        self.assertIn(youtube.FORBIDDEN_MARKER, text)


class Format(unittest.TestCase):
    def test_hls_h264_first_and_original_audio(self):
        video, audio = youtube.FORMAT.split(",")
        self.assertTrue(video.startswith("(bv*[protocol^=m3u8][vcodec^=avc1][height<=480][aspect_ratio>=1]/"))
        self.assertIn("[width<=480][aspect_ratio<1]", video)
        self.assertTrue(audio.startswith("(ba[format_note*=original]/"))


if __name__ == "__main__":
    unittest.main()
