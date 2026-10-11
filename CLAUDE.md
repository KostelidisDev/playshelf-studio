# CLAUDE.md

PlayShelf Studio is a Tkinter desktop app that edits the PlayShelf catalog
(games plus YouTube videos) and exports the site's `videos.csv`. It is pure
standard-library Python. PyInstaller (with certifi) is only for building the
executable.

## Commands

```sh
python -m playshelf_studio                 # run the app
python -m unittest                         # all tests (from repo root)
python -m unittest tests.test_library      # one module
python build.py [version]                  # build executable into dist/
PLAYSHELF_STUDIO_DATA_DIR=/tmp/ps python -m playshelf_studio   # throwaway data folder
```

The local venv is `.venv/` (Python 3.14).

The CI is `.github/workflows/build.yml`. It runs `flake8` (max line length 127) 
and the tests on all three OSes, then builds macOS, Windows and Linux on
x64 and arm64. A `v*.*.*` tag publishes a GitHub Release.

## Architecture

The code is split into layers. **Each layer only imports from the layers above
it:**

```
utils    text cleaning, game_key, YouTube id/URL + oEmbed title, dates
core     models (frozen dataclasses), validation, Library service, ABC interfaces, errors
storage  CsvRepository (games.csv + videos.csv), SiteCsvFormat, low-level csv_files
config   data folder (paths), Settings (JSON), logging
ui       Tkinter: App, GameSidebar, VideoList, VideoDetail, dialogs, widgets
```

- `playshelf_studio/__init__.py:main` is the composition root. It wires
  `CsvRepository` and `SiteCsvFormat` into `Library`, then hands `Library` and
  `Settings` to `App`.
- **`Library` (`core/library.py`) holds every domain rule.** The UI never
  touches files; every data change goes through `Library`.
- **The state is immutable.** `LibraryData` is a frozen dataclass of tuples.
  Each change goes through `_commit` in this order: `normalize()` builds the
  new state, `repository.save()` runs, and only then `_set()` makes the state
  current. A failed save leaves memory and disk in agreement. Undo and redo
  just keep earlier `LibraryData` snapshots (`MAX_UNDO = 100`).
- `normalize()` de-duplicates games case-insensitively (the first spelling
  wins), gives every video's `game_title` the canonical spelling, adds games
  that videos reference, and sorts videos newest first.
- `CsvRepository` detects conflicts by comparing the `(mtime_ns, size)` of
  both files with the values from the last load or save. If they differ, the
  save is refused with `ConflictError`, and the UI then reloads.
- Writes are atomic (temp file in the same folder, fsync, then `os.replace`).
- `tests/fakes.py:MemoryRepository` is an in-memory `LibraryRepository` for
  core tests.

## Conventions

- **Errors**: expected failures subclass `PlayShelfError`. The UI shows
  `ValidationError` messages to users as they are, so write those messages for
  users. Storage turns `OSError` into `StorageError`, and turns problems with
  an imported file into `ImportFormatError`.
- **Game identity** is `utils.text.game_key()` (cleaned and casefolded, and
  `lru_cache`d). Never compare raw game titles.
- **Text input** passes through `utils.text.clean()`. It strips control and
  bidi-override characters and collapses whitespace.
- **Video ids** must match `VIDEO_ID_RE`. Anything that builds a URL or path
  from an id relies on that, so use `watch_url()` and `parse_video_id()`
  rather than building strings by hand.
- **Dates** are stored as `YYYY-MM-DDTHH:MM:SSZ` in UTC (`utils/dates.py`).
  They are shown in local time.
- **The site CSV columns (`video_id,title,published_at,game_title`) are an
  external contract.** Don't change them.
- **Tk is not thread-safe.** Background work (the oEmbed title fetch) runs on
  a daemon thread, and the UI thread polls it with `after()`.
- **Code style**: plain functions and classes, short docstrings that explain
  *why*, no type-hint requirement, and only the standard library at runtime.
  Lines run up to about 120 characters.
- **Tests** use `unittest`, not pytest. Use `tempfile.TemporaryDirectory()`
  with `addCleanup` for anything that touches disk. The UI layer has no unit
  tests, so to check a UI change, run the app with a throwaway
  `PLAYSHELF_STUDIO_DATA_DIR`.
