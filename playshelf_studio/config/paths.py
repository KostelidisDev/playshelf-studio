"""Where the app keeps its files.

The per-user data folder of each OS, unless PLAYSHELF_STUDIO_DATA_DIR is set:

    Windows  %APPDATA%\\PlayShelfStudio
    macOS    ~/Library/Application Support/PlayShelfStudio
    Linux    $XDG_DATA_HOME/playshelf-studio (~/.local/share/playshelf-studio)
"""

import os
import sys
from pathlib import Path

APP_NAME = "PlayShelf Studio"
ENV_DATA_DIR = "PLAYSHELF_STUDIO_DATA_DIR"


def _folder(name, linux_name):
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming") / name
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / name
    return Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share") / linux_name


def data_dir():
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override).expanduser().resolve()
    return _folder("PlayShelfStudio", "playshelf-studio")


def log_dir(base=None):
    return Path(base or data_dir()) / "logs"
