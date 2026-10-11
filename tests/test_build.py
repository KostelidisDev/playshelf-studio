import io
import plistlib
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from build import (ENV_VERSION, notary_auth, resolve_version, stamp_bundle_version, version_numbers,
                   write_windows_version_info)


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


class NotaryAuthTest(unittest.TestCase):
    API_KEY = {"NOTARY_API_KEY_PATH": "/k.p8", "NOTARY_API_KEY_ID": "ABC", "NOTARY_API_ISSUER_ID": "uuid"}

    def test_keychain_profile_wins(self):
        self.assertEqual(notary_auth({"NOTARY_KEYCHAIN_PROFILE": "ps", **self.API_KEY}), ["--keychain-profile", "ps"])

    def test_api_key(self):
        self.assertEqual(notary_auth(self.API_KEY), ["--key", "/k.p8", "--key-id", "ABC", "--issuer", "uuid"])

    def test_incomplete_api_key_means_none(self):
        self.assertIsNone(notary_auth({**self.API_KEY, "NOTARY_API_KEY_ID": ""}))


class WindowsVersionInfoTest(unittest.TestCase):
    def write(self, version):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return write_windows_version_info(Path(tmp.name) / "build" / "version_info.txt", version).read_text()

    def test_numbers(self):
        self.assertEqual(version_numbers("v2026.10.08-build203015"), (2026, 10, 8, 203015))
        self.assertEqual(version_numbers("1.2.0-rc1"), (1, 2, 0, 0))
        self.assertIsNone(version_numbers("abc1234"))

    def test_clock_version(self):
        text = self.write("v2026.10.08-build203015")
        self.assertIn("filevers=(2026, 10, 8, 0)", text)
        self.assertIn("StringStruct('ProductVersion', 'v2026.10.08-build203015')", text)
        self.assertIn("StringStruct('ProductName', 'PlayShelf Studio')", text)

    def test_commit_hash_version(self):
        text = self.write("abc1234")
        self.assertIn("prodvers=(0, 0, 0, 0)", text)
        self.assertIn("StringStruct('FileVersion', 'abc1234')", text)
