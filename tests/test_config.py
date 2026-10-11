import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from playshelf_studio.config import Settings, paths


class DataDirTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = {"XDG_DATA_HOME": str(self.root)}
        patches = [mock.patch.object(paths.sys, "platform", "linux"), mock.patch.dict(os.environ, env)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop(paths.ENV_DATA_DIR, None)

    def test_env_override(self):
        with mock.patch.dict(os.environ, {paths.ENV_DATA_DIR: str(self.root / "custom")}):
            self.assertEqual(paths.data_dir(), (self.root / "custom").resolve())

    def test_default_folder(self):
        self.assertEqual(paths.data_dir(), self.root / "playshelf-studio")


class SettingsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_values_persist(self):
        Settings(self.dir).update({"a": "x", "b": 2})
        settings = Settings(self.dir)
        self.assertEqual((settings.get("a"), settings.get("b")), ("x", 2))

    def test_unreadable_file_is_ignored(self):
        (self.dir / "settings.json").write_text("{not json", encoding="utf-8")
        with self.assertLogs("playshelf_studio.config.settings", "WARNING"):
            settings = Settings(self.dir)
        self.assertEqual(settings.get("a", "default"), "default")

    def test_existing_dir_falls_back_to_home(self):
        settings = Settings(self.dir)
        settings.set("folder", str(self.dir / "gone"))
        self.assertEqual(settings.get_existing_dir("folder"), str(Path.home()))
