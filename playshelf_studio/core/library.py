"""The Library: every rule about games and videos, independent of the UI and
of how the data is stored (that's the LibraryRepository's job).

Each change builds the new state, saves it, and only then makes it current,
so a failed save (disk full, file locked, conflict) leaves memory and disk
in agreement. LibraryData is immutable, so undo/redo just keeps the previous
states around.
"""

import hashlib
from dataclasses import replace

from ..utils.text import clean, game_key
from .errors import ValidationError
from .interfaces import LibraryRepository, SiteFormat
from .models import ImportReport, LibraryData, Video
from .validation import validate_game_title, validate_video

MAX_UNDO = 100


def normalize(games, videos):
    """Returns consistent LibraryData from possibly messy input:

    - games de-duplicated case-insensitively (first spelling wins), sorted;
    - each video's game_title spelled as in the games list, and any game a
      video uses but the list lacks is added;
    - videos de-duplicated by id (first wins), newest first.
    """
    by_key = {}
    for title in games:
        title = clean(title)
        if title:
            by_key.setdefault(game_key(title), title)

    seen = set()
    linked = []
    for video in videos:
        if video.video_id in seen:
            continue
        seen.add(video.video_id)
        if video.game_title:
            canonical = by_key.setdefault(game_key(video.game_title), clean(video.game_title))
            video = replace(video, game_title=canonical)
        linked.append(video)

    return LibraryData(
        games=tuple(sorted(by_key.values(), key=game_key)),
        videos=tuple(sorted(linked, key=lambda v: v.published_at, reverse=True)),
    )


class Library:
    def __init__(self, repository: LibraryRepository, site_format: SiteFormat):
        self._repository = repository
        self._site_format = site_format
        self._set(LibraryData())
        self._undo = []  # of (LibraryData before the change, label)
        self._redo = []  # of (LibraryData after the change, label)

    # ---------- State ----------

    def _set(self, data):
        """Makes `data` current; the id index keeps find_video O(1)."""
        self._data = data
        self._by_id = {v.video_id: v for v in data.videos}

    @property
    def games(self):
        return self._data.games

    @property
    def videos(self):
        return self._data.videos

    @property
    def location(self):
        return self._repository.location

    def exists(self):
        return self._repository.exists()

    def load(self):
        """(Re)reads the stored data. Returns the rows that had to be skipped."""
        data, skipped = self._repository.load()
        self._set(normalize(data.games, data.videos))
        self._undo.clear()  # the history may not match what's on disk any more
        self._redo.clear()
        return skipped

    def initialize_empty(self):
        self._commit((), (), None)

    def _commit(self, games, videos, label):
        """Saves a new state; `label` names the change for Undo (None: not undoable)."""
        data = normalize(games, videos)
        before = self._data
        self._repository.save(data)
        self._set(data)
        if label:
            self._undo = (self._undo + [(before, label)])[-MAX_UNDO:]
            self._redo.clear()
        return data

    # ---------- Undo / redo ----------

    @property
    def undo_label(self):
        """What Undo would revert, or None."""
        return self._undo[-1][1] if self._undo else None

    @property
    def redo_label(self):
        return self._redo[-1][1] if self._redo else None

    def undo(self):
        """Reverts the last change. Returns its label, or None if there was none."""
        return self._travel(self._undo, self._redo)

    def redo(self):
        return self._travel(self._redo, self._undo)

    def _travel(self, source, target):
        if not source:
            return None
        data, label = source[-1]
        self._repository.save(data)
        source.pop()
        target.append((self._data, label))
        self._set(data)
        return label

    # ---------- Import / export ----------

    def import_site_csv(self, path):
        """Replaces everything with the contents of a site CSV, after backing
        the current data up. Returns an ImportReport."""
        data, skipped = self._site_format.read(path)
        self._repository.backup("before-import")
        data = self._commit(data.games, data.videos, "import")
        return ImportReport(videos=len(data.videos), games=len(data.games), skipped=tuple(skipped))

    def add_games(self, titles):
        """Adds every title not already in the list. Returns how many were new."""
        new = []
        keys = {game_key(g) for g in self.games}
        for title in titles:
            try:
                title = validate_game_title(title)
            except ValidationError:
                continue
            key = game_key(title)
            if key not in keys:
                keys.add(key)
                new.append(title)
        if new:
            self._commit(self.games + tuple(new), self.videos, "import games")
        return len(new)

    def export_site_csv(self, path):
        return self._site_format.write(path, self.videos)

    def export_fingerprint(self):
        """Changes whenever the exported site CSV would change (games without
        videos aren't exported), so the UI can tell if an export is stale."""
        digest = hashlib.sha256()
        for v in self.videos:
            digest.update(f"{v.video_id}\0{v.title}\0{v.published_at}\0{v.game_title}\n".encode())
        return digest.hexdigest()

    # ---------- Games ----------

    def find_game(self, title):
        key = game_key(title)
        return next((g for g in self.games if game_key(g) == key), None)

    def game_counts(self):
        """{game_key: number of videos}."""
        counts = {}
        for video in self.videos:
            if video.game_title:
                key = game_key(video.game_title)
                counts[key] = counts.get(key, 0) + 1
        return counts

    def video_count(self, game_title):
        return self.game_counts().get(game_key(game_title), 0)

    def add_game(self, title):
        title = validate_game_title(title)
        existing = self.find_game(title)
        if existing is not None:
            raise ValidationError(f"'{existing}' already exists.")
        self._commit(self.games + (title,), self.videos, "add game")
        return title

    def rename_game(self, old, new):
        """Renames a game and every video that uses it. Returns the new title."""
        new = validate_game_title(new)
        old_key = game_key(old)
        if self.find_game(old) is None:
            raise ValidationError(f"'{old}' isn't in the games list.")
        existing = self.find_game(new)
        if existing is not None and game_key(existing) != old_key:
            raise ValidationError(f"'{existing}' already exists.")
        games = tuple(new if game_key(g) == old_key else g for g in self.games)
        videos = tuple(
            replace(v, game_title=new) if game_key(v.game_title) == old_key else v
            for v in self.videos
        )
        self._commit(games, videos, "rename game")
        return new

    def delete_game(self, title):
        """Deletes a game; its videos are left without one."""
        key = game_key(title)
        games = tuple(g for g in self.games if game_key(g) != key)
        videos = tuple(replace(v, game_title="") if game_key(v.game_title) == key else v for v in self.videos)
        self._commit(games, videos, "delete game")

    # ---------- Videos ----------

    def find_video(self, video_id):
        return self._by_id.get(video_id)

    def _checked(self, video, original_id=None):
        video = validate_video(video)
        if video.video_id != original_id and self.find_video(video.video_id) is not None:
            raise ValidationError(f"A video with id {video.video_id} already exists.")
        if video.game_title:
            existing = self.find_game(video.game_title)
            if existing is None:
                raise ValidationError(f"'{video.game_title}' isn't in the games list.")
            video = replace(video, game_title=existing)
        return video

    def add_video(self, video: Video):
        video = self._checked(video)
        self._commit(self.games, self.videos + (video,), "add video")
        return video

    def update_video(self, original_id, video: Video):
        if self.find_video(original_id) is None:
            raise ValidationError(f"Video {original_id} no longer exists.")
        video = self._checked(video, original_id=original_id)
        self._commit(self.games, tuple(video if v.video_id == original_id else v for v in self.videos), "edit video")
        return video

    def set_game(self, video_ids, game_title):
        """Assigns one game (or none, with "") to several videos. Returns the
        game as spelled in the games list."""
        game = ""
        if (game_title or "").strip():
            game = self.find_game(game_title)
            if game is None:
                raise ValidationError(f"'{game_title.strip()}' isn't in the games list.")
        ids = set(video_ids)
        label = "set game" if len(ids) == 1 else f"set game of {len(ids)} videos"
        self._commit(self.games, tuple(replace(v, game_title=game) if v.video_id in ids else v for v in self.videos), label)
        return game

    def delete_videos(self, video_ids):
        ids = set(video_ids)
        label = "delete video" if len(ids) == 1 else f"delete {len(ids)} videos"
        self._commit(self.games, tuple(v for v in self.videos if v.video_id not in ids), label)
