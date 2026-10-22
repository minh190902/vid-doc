import unittest

from viddoc.transcript import parse_vtt

# The shape YouTube auto captions take: word timing tags, and each cue repeating the previous line.
ROLLING = """WEBVTT
Kind: captions
Language: en

00:00:00.060 --> 00:00:02.750 align:start position:0%

welcome<00:00:00.719><c> back</c><00:00:01.079><c> so</c>

00:00:02.750 --> 00:00:02.760 align:start position:0%
welcome back so

00:00:02.760 --> 00:00:05.030 align:start position:0%
welcome back so
having<00:00:03.120><c> trouble</c><00:00:03.419><c> with</c>

00:00:05.030 --> 00:00:05.040 align:start position:0%
having trouble with
"""

PLAIN = """WEBVTT

1
00:01:02.500 --> 00:01:04.000
Use three tones per material.

2
01:00:00.000 --> 01:00:01.000
Then add <i>one</i> highlight.
"""


class ParseVtt(unittest.TestCase):
    def test_rolling_captions_keep_each_line_once(self):
        segments = parse_vtt(ROLLING)
        self.assertEqual([s.text for s in segments], ["welcome back so", "having trouble with"])
        self.assertAlmostEqual(segments[1].start, 2.76)

    def test_plain_cues_and_hour_timestamps(self):
        segments = parse_vtt(PLAIN)
        self.assertEqual(segments[0].text, "Use three tones per material.")
        self.assertAlmostEqual(segments[0].start, 62.5)
        self.assertEqual(segments[1].text, "Then add one highlight.")
        self.assertAlmostEqual(segments[1].start, 3600.0)

    def test_html_entities_and_spacing(self):
        text = "WEBVTT\n\n00:00:03.000 --> 00:00:05.000\nshading pixel art are the&nbsp;&nbsp;\nlight&amp;shape\n"
        self.assertEqual(parse_vtt(text)[0].text, "shading pixel art are the light&shape")

    def test_crlf_input(self):
        self.assertEqual(len(parse_vtt(PLAIN.replace("\n", "\r\n"))), 2)


if __name__ == "__main__":
    unittest.main()
