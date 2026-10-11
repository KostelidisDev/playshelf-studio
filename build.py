#!/usr/bin/env python3
"""Builds the PlayShelf Studio executable for the current OS with PyInstaller.

    pip install -r requirements.txt
    python build.py                 # version from the environment or the clock
    python build.py v2026.10.08-build203015

The version is the first of:
    1. the command-line argument
    2. $PLAYSHELF_STUDIO_VERSION
    3. the tag on GitHub Actions ($GITHUB_REF_NAME when $GITHUB_REF_TYPE is
       "tag", which includes release builds)
    4. the current time

Output in dist/:
    Windows  PlayShelfStudio.exe       (single file)
    Linux    PlayShelfStudio           (single file)
    macOS    PlayShelfStudio.app       (app bundle; macOS discourages
                                        single-file windowed executables)

PyInstaller can't cross-compile: build on each OS you want to ship for.
The fallback uses the same format as the site: v<Y>.<M>.<D>-build<HHMMSS>.

macOS signing (optional; without it the bundle is signed ad hoc):
    MACOS_CODESIGN_IDENTITY   "Developer ID Application: <Name> (<TEAMID>)",
                              in a keychain codesign can reach
and, to also notarize and staple, either
    NOTARY_KEYCHAIN_PROFILE   a profile saved by `xcrun notarytool store-credentials`
or an App Store Connect API key:
    NOTARY_API_KEY_PATH       the AuthKey_<id>.p8 file
    NOTARY_API_KEY_ID
    NOTARY_API_ISSUER_ID
Windows signing happens in CI after the build (see .github/workflows/build.yml).
"""

import json
import os
import plistlib
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION_FILE = HERE / "playshelf_studio" / "_version.py"
NAME = "PlayShelfStudio"
ENV_VERSION = "PLAYSHELF_STUDIO_VERSION"
PRODUCT = "PlayShelf Studio"
PUBLISHER = "Kostelidis.dev"
BUNDLE_ID = "dev.kostelidis.playshelfstudio"
ENTITLEMENTS = HERE / "packaging" / "entitlements.plist"


def resolve_version(argv, env):
    candidates = [
        argv[1] if len(argv) > 1 else "",
        env.get(ENV_VERSION, ""),
        env.get("GITHUB_REF_NAME", "") if env.get("GITHUB_REF_TYPE") == "tag" else "",
    ]
    for candidate in candidates:
        if candidate.strip():
            return candidate.strip()
    return datetime.now().strftime("v%Y.%m.%d-build%H%M%S")


def main():
    import PyInstaller.__main__

    version = resolve_version(sys.argv, os.environ)
    identity = os.environ.get("MACOS_CODESIGN_IDENTITY", "").strip() if sys.platform == "darwin" else ""
    original = VERSION_FILE.read_text(encoding="utf-8")
    VERSION_FILE.write_text(f'# Stamped by build.py.\n__version__ = {version!r}\n', encoding="utf-8")
    try:
        args = [
            str(HERE / "playshelf_studio" / "__main__.py"),
            "--name", NAME,
            "--windowed",
            "--noconfirm",
            "--clean",
            "--paths", str(HERE),
            "--distpath", str(HERE / "dist"),
            "--workpath", str(HERE / "build"),
            "--specpath", str(HERE / "build"),
        ]
        if sys.platform == "darwin":
            args += ["--osx-bundle-identifier", BUNDLE_ID]
            if identity:
                # PyInstaller signs every nested binary with the hardened runtime.
                args += ["--codesign-identity", identity, "--osx-entitlements-file", str(ENTITLEMENTS)]
        else:
            args.append("--onefile")
        if sys.platform == "win32":
            args += ["--version-file", str(write_windows_version_info(HERE / "build" / "version_info.txt", version))]
        PyInstaller.__main__.run(args)
    finally:
        VERSION_FILE.write_text(original, encoding="utf-8")
    if sys.platform == "darwin":
        bundle = HERE / "dist" / f"{NAME}.app"
        if identity:
            stamp_bundle_version(bundle / "Contents" / "Info.plist", version)
            # Info.plist is covered by the bundle's seal, so re-seal it. The nested code is already signed.
            subprocess.run(["codesign", "--force", "--timestamp", "--options", "runtime",
                            "--entitlements", str(ENTITLEMENTS), "--sign", identity, str(bundle)], check=True)
            subprocess.run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(bundle)], check=True)
            notarize(bundle)
        elif stamp_bundle_version(bundle / "Contents" / "Info.plist", version):
            # Info.plist is covered by the signature; re-sign ad hoc like PyInstaller did.
            subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(bundle)], check=True)
    print(f"Built {NAME} {version} in {HERE / 'dist'}")


def notary_auth(env):
    """notarytool's credential arguments, or None when no credentials are set."""
    if env.get("NOTARY_KEYCHAIN_PROFILE"):
        return ["--keychain-profile", env["NOTARY_KEYCHAIN_PROFILE"]]
    keys = ("NOTARY_API_KEY_PATH", "NOTARY_API_KEY_ID", "NOTARY_API_ISSUER_ID")
    if all(env.get(k) for k in keys):
        return ["--key", env[keys[0]], "--key-id", env[keys[1]], "--issuer", env[keys[2]]]
    return None


def notarize(bundle):
    """Notarizes and staples the bundle so Gatekeeper accepts it offline, on first launch."""
    auth = notary_auth(os.environ)
    if auth is None:
        print("Warning: no notarization credentials; the app is signed but not notarized")
        return
    archive = HERE / "build" / f"{NAME}-notarize.zip"
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(bundle), str(archive)], check=True)
    # notarytool exits 0 even when Apple rejects the upload, so check the status it reports.
    result = subprocess.run(["xcrun", "notarytool", "submit", str(archive), *auth, "--wait",
                             "--output-format", "json"], check=True, capture_output=True, text=True)
    archive.unlink()
    submission = json.loads(result.stdout)
    if submission.get("status") != "Accepted":
        subprocess.run(["xcrun", "notarytool", "log", submission.get("id", ""), *auth])
        sys.exit(f"Notarization failed: {submission}")
    subprocess.run(["xcrun", "stapler", "staple", str(bundle)], check=True)
    subprocess.run(["spctl", "--assess", "--type", "execute", "--verbose=2", str(bundle)], check=True)


def stamp_bundle_version(plist_path, version):
    """PyInstaller leaves the bundle at 0.0.0, which Finder's Get Info shows.

    macOS wants dotted integers: v2026.10.08-build203015 becomes 2026.10.8
    (CFBundleShortVersionString) and 2026.10.8.203015 (CFBundleVersion); a
    tag like v1.2.0-rc1 becomes 1.2.0.
    """
    numbers = version_numbers(version)
    if not numbers:
        print(f"Warning: {version!r} doesn't start with [v]<X>.<Y>.<Z>; bundle version left as is")
        return False
    year, month, day, build = numbers
    short = f"{year}.{month}.{day}"
    with plist_path.open("rb") as f:
        info = plistlib.load(f)
    info["CFBundleShortVersionString"] = short
    info["CFBundleVersion"] = f"{short}.{build}" if build else short
    with plist_path.open("wb") as f:
        plistlib.dump(info, f)
    return True


def version_numbers(version):
    """(X, Y, Z, build) as ints from [v]X.Y.Z[-build<N>], with build 0 when absent; None for anything else."""
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)(?:-build(\d+))?", version)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def write_windows_version_info(path, version):
    """Writes the PyInstaller version resource, so the exe names its product and version.

    SignPath only signs executables whose metadata names the product. The
    numeric fields hold 16 bits each, so a -build<HHMMSS> suffix is left to
    the version strings, and a commit-hash version shows as 0.0.0.0.
    """
    x, y, z, _ = version_numbers(version) or (0, 0, 0, 0)
    numbers = (x, y, z, 0)
    strings = {
        "CompanyName": PUBLISHER,
        "FileDescription": PRODUCT,
        "FileVersion": version,
        "InternalName": NAME,
        "LegalCopyright": f"Copyright (c) {PUBLISHER}. MIT License.",
        "OriginalFilename": f"{NAME}.exe",
        "ProductName": PRODUCT,
        "ProductVersion": version,
    }
    table = ", ".join(f"StringStruct({k!r}, {v!r})" for k, v in strings.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"VSVersionInfo(ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}), kids=[\n"
        f"  StringFileInfo([StringTable('040904B0', [{table}])]),\n"
        f"  VarFileInfo([VarStruct('Translation', [1033, 1200])]),\n"
        f"])\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    main()
