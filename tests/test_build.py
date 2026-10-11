import io
import plistlib
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from build import ENV_VERSION, resolve_version, stamp_bundle_version


class ResolveVersionTest(unittest.TestCase):
    TAG_ENV = {"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v1.2.0"}

    def test_argument_wins(self):
        self.assertEqual(resolve_version(["build.py", "v9"], {ENV_VERSION: "v8", **self.TAG_ENV}), "v9")

    def test_env_variable_over_tag(self):
        self.assertEqual(resolve_version(["build.py"], {ENV_VERSION: " v8 ", **self.TAG_ENV}), "v8")

    def test_github_tag(self):
        self.assertEqual(resolve_version(["build.py"], self.TAG_ENV), "v1.2.0")

    def test_github_branch_is_ignored(self):
        version = resolve_version(["build.py"], {"GITHUB_REF_TYPE": "branch", "GITHUB_REF_NAME": "main"})
        self.assertRegex(version, r"^v\d{4}\.\d{2}\.\d{2}-build\d{6}$")

    def test_blank_values_fall_back_to_clock(self):
        self.assertRegex(resolve_version(["build.py", ""], {ENV_VERSION: "  "}), r"^v\d{4}\.")


class StampBundleVersionTest(unittest.TestCase):
    def stamp(self, version):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "Info.plist"
        path.write_bytes(plistlib.dumps({"CFBundleShortVersionString": "0.0.0"}))
        changed = stamp_bundle_version(path, version)
        info = plistlib.loads(path.read_bytes())
        return changed, info["CFBundleShortVersionString"], info.get("CFBundleVersion")

    def test_clock_version(self):
        self.assertEqual(self.stamp("v2026.10.08-build203015"), (True, "2026.10.8", "2026.10.8.203015"))

    def test_tag_with_suffix(self):
        self.assertEqual(self.stamp("v1.2.0-rc1"), (True, "1.2.0", "1.2.0"))

    def test_unparseable_left_alone(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(self.stamp("nightly"), (False, "0.0.0", None))
        self.assertIn("'nightly'", out.getvalue())
