"""Small JSON key/value store for UI conveniences (last used folders...).

Never holds data that matters: unreadable or unwritable settings are
silently ignored.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"


class Settings:
    def __init__(self, directory):
        self._path = Path(directory) / SETTINGS_FILE
        self._values = {}
        try:
            values = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(values, dict):
                self._values = values
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            log.warning("Ignoring unreadable %s: %s", self._path, e)

    def get(self, key, default=None):
        value = self._values.get(key, default)
        return value if isinstance(value, (str, int, float, bool)) or value is None else default

    def get_existing_dir(self, key):
        """A remembered folder, only if it still exists (else the home folder)."""
        value = self.get(key)
        return value if isinstance(value, str) and Path(value).is_dir() else str(Path.home())

    def set(self, key, value):
        self.update({key: value})

    def update(self, values):
        """Sets several keys with a single write."""
        self._values.update(values)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".settings.", dir=self._path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._values, f, indent=2)
            os.replace(tmp, self._path)
        except OSError as e:
            log.warning("Couldn't save settings: %s", e)
