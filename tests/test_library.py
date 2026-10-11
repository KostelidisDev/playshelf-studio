import unittest

from playshelf_studio.core import Library, LibraryData, StorageError, ValidationError, Video
from playshelf_studio.storage import SiteCsvFormat

from .fakes import MemoryRepository

VIDEOS = (
    Video("tW8maoQNthw", "Horror Night", "2022-06-20T11:02:29Z", "Scary Game"),
    Video("GoWP3HNfS9M", "Spyro run", "2023-10-30T11:30:06Z", "Spyro the Dragon"),
    Video("sJycQG5bMuk", "Deceit", "2024-05-09T10:30:30Z", "scary  game"),
    Video("FWutpsH_haw", "No game", "2023-11-06T11:30:07Z", ""),
)


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.repo = MemoryRepository(LibraryData(games=("Scary Game", "Spyro the Dragon"), videos=VIDEOS))
        self.library = Library(self.repo, SiteCsvFormat())
        self.library.load()

    def test_load_normalizes(self):
        self.assertEqual(self.library.games, ("Scary Game", "Spyro the Dragon"))
        self.assertEqual(self.library.find_video("sJycQG5bMuk").game_title, "Scary Game")
        self.assertEqual(self.library.videos[0].video_id, "sJycQG5bMuk")  # newest first

    def test_load_adds_games_only_referenced_by_videos(self):
        self.repo.data = LibraryData(games=(), videos=VIDEOS)
        self.library.load()
        self.assertEqual(self.library.games, ("Scary Game", "Spyro the Dragon"))

    def test_rename_game_cascades(self):
        self.library.rename_game("scary game", "Amnesia")
        self.assertIn("Amnesia", self.library.games)
        self.assertEqual(self.library.video_count("Amnesia"), 2)
        self.assertEqual(self.repo.data, self.library._data)

    def test_rename_to_existing_or_missing_game_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.library.rename_game("Scary Game", "SPYRO the dragon")
        with self.assertRaises(ValidationError):
            self.library.rename_game("Nope", "Other")

    def test_rename_can_change_case_only(self):
        self.library.rename_game("Scary Game", "SCARY GAME")
        self.assertIn("SCARY GAME", self.library.games)

    def test_delete_game_unassigns_videos(self):
        self.library.delete_game("Spyro the Dragon")
        self.assertNotIn("Spyro the Dragon", self.library.games)
        self.assertEqual(self.library.find_video("GoWP3HNfS9M").game_title, "")

    def test_add_video_validates(self):
        video = self.library.add_video(Video("https://youtu.be/abcdefghijk", " A ‮ title ", "2024-01-02", "spyro THE dragon"))
        self.assertEqual(video, Video("abcdefghijk", "A title", "2024-01-02T00:00:00Z", "Spyro the Dragon"))
        bad = [
            Video("bbbbbbbbbbb", "x", "2024-01-02", "Unknown game"),
            Video("abcdefghijk", "duplicate", "2024-01-02", ""),
            Video("not an id", "x", "2024-01-02", ""),
            Video("ccccccccccc", "", "2024-01-02", ""),
            Video("ccccccccccc", "x" * 500, "2024-01-02", ""),
            Video("ccccccccccc", "x", "someday", ""),
        ]
        for video in bad:
            with self.assertRaises(ValidationError, msg=video):
                self.library.add_video(video)

    def test_update_video_can_change_id(self):
        self.library.update_video("FWutpsH_haw", Video("FWutpsH_hax", "Renamed", "2023-11-06T11:30:07Z", "Scary Game"))
        self.assertIsNone(self.library.find_video("FWutpsH_haw"))
        self.assertEqual(self.library.find_video("FWutpsH_hax").title, "Renamed")

    def test_failed_save_leaves_state_unchanged(self):
        before = self.library._data
        self.repo.fail_with = StorageError("disk full")
        with self.assertRaises(StorageError):
            self.library.delete_videos(["tW8maoQNthw"])
        self.assertIs(self.library._data, before)
        self.assertIsNotNone(self.library.find_video("tW8maoQNthw"))

    def test_add_games(self):
        self.assertEqual(self.library.add_games(["New", "scary game", "", "new", "x" * 500]), 1)
        self.assertIn("New", self.library.games)

    def test_undo_redo(self):
        self.library.delete_videos(["tW8maoQNthw"])
        self.library.rename_game("Spyro the Dragon", "Spyro")
        self.assertEqual(self.library.undo_label, "rename game")
        self.assertEqual(self.library.undo(), "rename game")
        self.assertIn("Spyro the Dragon", self.library.games)
        self.assertEqual(self.library.undo(), "delete video")
        self.assertIsNotNone(self.library.find_video("tW8maoQNthw"))
        self.assertIsNone(self.library.undo())
        self.assertEqual(self.repo.data, self.library._data)  # undo is saved
        self.assertEqual(self.library.redo(), "delete video")
        self.assertIsNone(self.library.find_video("tW8maoQNthw"))
        self.assertEqual(self.library.redo_label, "rename game")

    def test_new_change_clears_redo_and_load_clears_history(self):
        self.library.delete_videos(["tW8maoQNthw"])
        self.library.undo()
        self.library.add_game("New")
        self.assertIsNone(self.library.redo_label)
        self.library.load()
        self.assertIsNone(self.library.undo_label)

    def test_failed_undo_keeps_history(self):
        self.library.delete_videos(["tW8maoQNthw"])
        self.repo.fail_with = StorageError("disk full")
        with self.assertRaises(StorageError):
            self.library.undo()
        self.assertEqual(self.library.undo_label, "delete video")
        self.assertIsNone(self.library.find_video("tW8maoQNthw"))

    def test_set_game(self):
        self.assertEqual(self.library.set_game(["FWutpsH_haw", "GoWP3HNfS9M"], "scary GAME"), "Scary Game")
        self.assertEqual(self.library.video_count("Scary Game"), 4)
        self.library.set_game(["FWutpsH_haw"], "")
        self.assertEqual(self.library.find_video("FWutpsH_haw").game_title, "")
        with self.assertRaises(ValidationError):
            self.library.set_game(["FWutpsH_haw"], "Unknown")

    def test_export_fingerprint_ignores_unused_games(self):
        before = self.library.export_fingerprint()
        self.library.add_game("Unused")
        self.assertEqual(self.library.export_fingerprint(), before)
        self.library.rename_game("Spyro the Dragon", "Spyro")
        self.assertNotEqual(self.library.export_fingerprint(), before)


if __name__ == "__main__":
    unittest.main()
