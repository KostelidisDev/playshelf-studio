"""LibraryRepository backed by two CSV files in a folder:

    games.csv   title
    videos.csv  video_id, title, published_at, game_title

Plain CSV so the data stays readable and editable without the app. Before
every save the files' signatures are compared with the ones last read or
written; if another program (or a second copy of the app) changed them in
between, the save is refused with a ConflictError instead of overwriting.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from ..core.errors import ConflictError, ImportFormatError, StorageError, ValidationError
from ..core.interfaces import LibraryRepository
from ..core.models import LibraryData, SkippedRow
from ..core.validation import validate_game_title
from .csv_files import read_rows, signature, write_rows
from .video_rows import VIDEO_FIELDS, rows_to_videos, video_to_row

log = logging.getLogger(__name__)

GAMES_FILE = "games.csv"
VIDEOS_FILE = "videos.csv"
BACKUPS_DIR = "backups"
KEEP_BACKUPS = 20


class CsvRepository(LibraryRepository):
    def __init__(self, directory):
        self.directory = Path(directory)
        self._signatures = self._current_signatures()

    @property
    def location(self):
        return str(self.directory)

    @property
    def games_path(self):
        return self.directory / GAMES_FILE

    @property
    def videos_path(self):
        return self.directory / VIDEOS_FILE

    def exists(self):
        return self.games_path.exists() and self.videos_path.exists()

    def _current_signatures(self):
        return signature(self.games_path), signature(self.videos_path)

    def load(self):
        signatures = self._current_signatures()
        try:
            game_fields, game_rows = read_rows(self.games_path)
            video_fields, video_rows = read_rows(self.videos_path)
            if "title" not in game_fields:
                raise ImportFormatError(f"{GAMES_FILE} is missing the 'title' column.")
            videos, skipped = rows_to_videos(video_fields, video_rows, VIDEOS_FILE)
        except ImportFormatError as e:
            raise StorageError(str(e)) from None

        games = []
        for line, row in game_rows:
            try:
                games.append(validate_game_title(row.get("title")))
            except ValidationError as e:
                if (row.get("title") or "").strip():
                    skipped.append(SkippedRow(line, f"{GAMES_FILE}: {e}"))
        for row in skipped:
            log.warning("Skipped row on load: line %s: %s", row.line, row.reason)

        self._signatures = signatures
        return LibraryData(games=tuple(games), videos=tuple(videos)), skipped

    def save(self, data):
        if self._current_signatures() != self._signatures:
            raise ConflictError(
                "The data files were changed outside this window (another copy of "
                "PlayShelf Studio, or another program) since they were loaded."
            )
        write_rows(self.videos_path, VIDEO_FIELDS, [video_to_row(v) for v in data.videos])
        write_rows(self.games_path, ["title"], [{"title": g} for g in data.games])
        self._signatures = self._current_signatures()

    def backup(self, reason):
        files = [p for p in (self.games_path, self.videos_path) if p.exists()]
        if not files:
            return None
        target = self.directory / BACKUPS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{reason}"
        try:
            target.mkdir(parents=True, exist_ok=True)
            for path in files:
                shutil.copy2(path, target / path.name)
        except OSError as e:
            raise StorageError(f"Couldn't back up the current data: {e.strerror or e}") from None
        self._prune_backups()
        log.info("Backed up data to %s", target)
        return str(target)

    def _prune_backups(self):
        backups = sorted((p for p in (self.directory / BACKUPS_DIR).iterdir() if p.is_dir()), reverse=True)
        for old in backups[KEEP_BACKUPS:]:
            shutil.rmtree(old, ignore_errors=True)
