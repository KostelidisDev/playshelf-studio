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
"""

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
        if sys.platform != "darwin":
            args.append("--onefile")
        PyInstaller.__main__.run(args)
    finally:
        VERSION_FILE.write_text(original, encoding="utf-8")
    if sys.platform == "darwin":
        bundle = HERE / "dist" / f"{NAME}.app"
        if stamp_bundle_version(bundle / "Contents" / "Info.plist", version):
            # Info.plist is covered by the signature; re-sign ad hoc like PyInstaller did.
            subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(bundle)], check=True)
    print(f"Built {NAME} {version} in {HERE / 'dist'}")


def stamp_bundle_version(plist_path, version):
    """PyInstaller leaves the bundle at 0.0.0, which Finder's Get Info shows.

    macOS wants dotted integers: v2026.10.08-build203015 becomes 2026.10.8
    (CFBundleShortVersionString) and 2026.10.8.203015 (CFBundleVersion); a
    tag like v1.2.0-rc1 becomes 1.2.0.
    """
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)(?:-build(\d+))?", version)
    if not match:
        print(f"Warning: {version!r} doesn't start with [v]<X>.<Y>.<Z>; bundle version left as is")
        return False
    year, month, day, build = match.groups()
    short = f"{int(year)}.{int(month)}.{int(day)}"
    with plist_path.open("rb") as f:
        info = plistlib.load(f)
    info["CFBundleShortVersionString"] = short
    info["CFBundleVersion"] = f"{short}.{int(build)}" if build else short
    with plist_path.open("wb") as f:
        plistlib.dump(info, f)
    return True


if __name__ == "__main__":
    main()
