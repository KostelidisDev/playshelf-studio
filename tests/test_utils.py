import unittest
from datetime import timedelta, timezone

from playshelf_studio.utils.dates import format_local, format_published_at, parse_datetime
from playshelf_studio.utils.text import clean, game_key, to_site_csv_title
from playshelf_studio.utils.youtube import parse_video_id, watch_url


class TextTest(unittest.TestCase):
    def test_clean_strips_controls_and_bidi_overrides(self):
        self.assertEqual(clean(" a\tb\x00c\n d "), "a bc d")
        self.assertEqual(clean("evil‮txt.exe"), "eviltxt.exe")
        self.assertEqual(clean("x⁦y⁩"), "xy")

    def test_clean_keeps_emoji_joiners_and_non_latin(self):
        family = "👨‍👩‍👧"
        self.assertEqual(clean(f"Αμνησία {family}"), f"Αμνησία {family}")

    def test_game_key(self):
        self.assertEqual(game_key("  Scary   GAME "), game_key("scary game"))

    def test_site_csv_title(self):
        self.assertEqual(to_site_csv_title('Say "hi",\nall'), "Say 'hi'; all")


class YouTubeTest(unittest.TestCase):
    def test_parse_video_id_accepts_ids_and_youtube_urls(self):
        for text in [
            "abcdefghijk",
            "https://www.youtube.com/watch?v=abcdefghijk&t=1",
            "https://www.youtube.com/watch?feature=share&v=abcdefghijk",
            "https://youtube.com/shorts/abcdefghijk",
            "https://m.youtube.com/live/abcdefghijk?si=x",
            "youtu.be/abcdefghijk",
            "https://youtu.be/abcdefghijk?t=3",
        ]:
            self.assertEqual(parse_video_id(text), "abcdefghijk", text)

    def test_parse_video_id_rejects_everything_else(self):
        for text in [
            "short",
            "abcdefghijkl",
            "../../etc/pas",
            "https://evil.example/watch?v=abcdefghijk",
            "https://youtube.com.evil.example/abcdefghijk",
            "javascript:alert(1)//abcdefghijk",
            "abcdefghij\n",
        ]:
            self.assertIsNone(parse_video_id(text), text)

    def test_watch_url_requires_valid_id(self):
        self.assertEqual(watch_url("abcdefghijk"), "https://www.youtube.com/watch?v=abcdefghijk")
        with self.assertRaises(ValueError):
            watch_url("x&list=evil")


class DatesTest(unittest.TestCase):
    def test_parse_and_format(self):
        cases = {
            "2024-05-09T13:30:30+03:00": "2024-05-09T10:30:30Z",
            "2024-05-09T10:30:30Z": "2024-05-09T10:30:30Z",
            "2024-05-09T10:30:30.123Z": "2024-05-09T10:30:30Z",
            "2024-05-09": "2024-05-09T00:00:00Z",
        }
        for text, expected in cases.items():
            self.assertEqual(format_published_at(parse_datetime(text)), expected, text)
        for bad in ["", "yesterday", "2024-13-01"]:
            self.assertIsNone(parse_datetime(bad), bad)


class LocalDateTest(unittest.TestCase):
    def test_format_local(self):
        athens = timezone(timedelta(hours=2))
        self.assertEqual(format_local("2025-12-28T13:00:00Z", athens), "28 Dec 2025, 15:00")
        self.assertEqual(format_local("garbage", athens), "garbage")


if __name__ == "__main__":
    unittest.main()
