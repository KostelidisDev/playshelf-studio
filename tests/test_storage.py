import csv
import tempfile
import time
import unittest
from pathlib import Path

from playshelf_studio.core import ConflictError, ImportFormatError, Library, StorageError, Video
from playshelf_studio.storage import CsvRepository, SiteCsvFormat, read_first_column

SITE_CSV = """﻿video_id,title,published_at,game_title
tW8maoQNthw,Horror Night,2022-06-20T11:02:29Z,Scary Game
GoWP3HNfS9M,Spyro run,2023-10-30T11:30:06Z,Spyro the Dragon
sJycQG5bMuk,Deceit,2024-05-09T10:30:30Z,scary  game
FWutpsH_haw,No game,2023-11-06T11:30:07Z,
tW8maoQNthw,Duplicate,2022-06-20T11:02:29Z,Scary Game
../../evil1,Path traversal,2022-06-20T11:02:29Z,
abcdefghijk,Bad date,not-a-date,
"""


class StorageTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.site_csv = self.tmp / "site.csv"
        self.site_csv.write_text(SITE_CSV, encoding="utf-8")
        self.repo = CsvRepository(self.tmp / "data")
        self.library = Library(self.repo, SiteCsvFormat())
        self.report = self.library.import_site_csv(self.site_csv)

    def fresh_library(self):
        library = Library(CsvRepository(self.repo.directory), SiteCsvFormat())
        library.load()
        return library

    def test_import_skips_invalid_rows_and_reports_them(self):
        self.assertEqual((self.report.videos, self.report.games), (4, 2))
        self.assertEqual([s.line for s in self.report.skipped], [6, 7, 8])
        self.assertIn("duplicate", self.report.skipped[0].reason)
        self.assertIn("Skipped 3 row(s)", self.report.summary())

    def test_import_rejects_wrong_files(self):
        wrong = self.tmp / "wrong.csv"
        wrong.write_text("a,b\n1,2\n", encoding="utf-8")
        with self.assertRaises(ImportFormatError):
            self.library.import_site_csv(wrong)
        binary = self.tmp / "binary.csv"
        binary.write_bytes(b"\xff\xfe\x00\x81garbage")
        with self.assertRaises(ImportFormatError):
            self.library.import_site_csv(binary)
        with self.assertRaises(ImportFormatError):
            self.library.import_site_csv(self.tmp / "missing.csv")

    def test_changes_persist(self):
        self.library.rename_game("Scary Game", "Amnesia")
        self.assertEqual(self.fresh_library().video_count("Amnesia"), 2)

    def test_reimport_makes_backup(self):
        self.library.import_site_csv(self.site_csv)
        backups = list((self.repo.directory / "backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "videos.csv").exists())

    def test_external_change_is_detected(self):
        other = self.fresh_library()
        time.sleep(0.01)
        other.delete_videos(["tW8maoQNthw"])
        with self.assertRaises(ConflictError):
            self.library.add_game("Lost update")
        self.library.load()
        self.library.add_game("Saved after reload")
        self.assertIn("Saved after reload", self.fresh_library().games)

    def test_load_skips_hand_edited_garbage(self):
        with self.repo.videos_path.open("a", encoding="utf-8") as f:
            f.write("bad id!!!!!,x,2024-01-01T00:00:00Z,\n")
        library = Library(CsvRepository(self.repo.directory), SiteCsvFormat())
        with self.assertLogs("playshelf_studio.storage.csv_repository", "WARNING") as logs:
            skipped = library.load()
        self.assertIn("line 6", logs.output[0])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(len(library.videos), 4)

    def test_unreadable_data_is_storage_error(self):
        self.repo.videos_path.write_bytes(b"\xff\xfe\x81")
        with self.assertRaises(StorageError):
            Library(CsvRepository(self.repo.directory), SiteCsvFormat()).load()

    def test_export_matches_site_format(self):
        self.library.update_video("FWutpsH_haw", Video("FWutpsH_haw", 'Say "hi", all', "2023-11-06T11:30:07Z", ""))
        out = self.tmp / "out" / "videos.csv"
        self.assertEqual(self.library.export_site_csv(out), 4)
        self.assertTrue(out.read_bytes().startswith(b"\xef\xbb\xbf"))
        with out.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(list(rows[0]), ["video_id", "title", "published_at", "game_title"])
        self.assertEqual(rows[0]["video_id"], "sJycQG5bMuk")
        self.assertIn("Say 'hi'; all", [r["title"] for r in rows])

    def test_no_temp_files_left_behind(self):
        self.library.add_game("X")
        self.assertEqual([p.name for p in self.repo.directory.glob(".*.tmp")], [])

    def test_read_first_column(self):
        path = self.tmp / "games.csv"
        path.write_text("title\nNew Game\n\nOther,extra\n", encoding="utf-8")
        self.assertEqual(read_first_column(path), ["New Game", "Other"])


if __name__ == "__main__":
    unittest.main()
