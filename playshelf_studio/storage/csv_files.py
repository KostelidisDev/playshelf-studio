"""Low-level CSV file helpers: bounded reads, atomic writes, change detection."""

import csv
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..core.errors import ImportFormatError, StorageError

# The real site CSV is ~100 KB; anything this big is the wrong file.
MAX_FILE_BYTES = 20 * 1024 * 1024
ENCODING = "utf-8-sig"  # BOM on write so Excel detects UTF-8; tolerated on read


@contextmanager
def _open_csv(path):
    """Opens a CSV for reading, turning every way it can fail into an
    ImportFormatError (too large, not UTF-8, malformed, unreadable)."""
    path = Path(path)
    try:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ImportFormatError(f"{path.name} is too large ({size // 1024 // 1024} MB).")
        with path.open(encoding=ENCODING, newline="") as f:
            yield f
    except UnicodeDecodeError:
        raise ImportFormatError(f"{path.name} isn't a UTF-8 text file.") from None
    except csv.Error as e:
        raise ImportFormatError(f"{path.name} isn't a valid CSV file ({e}).") from None
    except OSError as e:
        raise ImportFormatError(f"Couldn't read {path.name}: {e.strerror or e}") from None


def read_rows(path):
    """Returns (fieldnames, [(line_number, row_dict)]). Raises ImportFormatError."""
    with _open_csv(path) as f:
        reader = csv.DictReader(f)
        rows = [(reader.line_num, row) for row in reader]
        return reader.fieldnames or [], rows


def read_first_column(path):
    """Values of the first column (skipping a `title` header). For title lists."""
    with _open_csv(path) as f:
        values = [row[0] for row in csv.reader(f) if row]
    if values and values[0].strip().lower() == "title":
        values = values[1:]
    return values


def write_rows(path, fieldnames, rows):
    """Writes atomically (temp file in the same folder, fsync, rename), so a
    crash or full disk never leaves a half-written file behind."""
    path = Path(path)
    tmp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "w", encoding=ENCODING, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None
    except PermissionError:
        raise StorageError(
            f"Couldn't write {path.name}: permission denied. "
            "If it's open in another program (e.g. Excel), close it and try again."
        ) from None
    except OSError as e:
        raise StorageError(f"Couldn't write {path.name}: {e.strerror or e}") from None
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def signature(path):
    """Cheap change detector: (mtime_ns, size), or None if the file is missing."""
    try:
        stat = Path(path).stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size
