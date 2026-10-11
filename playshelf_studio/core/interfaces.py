"""Interfaces between the core and its storage, so the Library doesn't care
where or how the data is kept (CSV files today; an in-memory fake in tests)."""

from abc import ABC, abstractmethod


class LibraryRepository(ABC):
    """Persists LibraryData."""

    @property
    @abstractmethod
    def location(self):
        """Human-readable description of where the data lives (shown in the UI)."""

    @abstractmethod
    def exists(self):
        """True once data has been saved at least once."""

    @abstractmethod
    def load(self):
        """Returns (LibraryData, [SkippedRow]) for rows that had to be dropped.

        Raises StorageError if the data can't be read.
        """

    @abstractmethod
    def save(self, data):
        """Persists `data` atomically.

        Raises ConflictError if the stored data changed since the last load or
        save through this repository, StorageError if it can't be written.
        """

    @abstractmethod
    def backup(self, reason):
        """Snapshots the current data before a destructive change. Returns a
        description of the backup, or None if there was nothing to back up."""


class SiteFormat(ABC):
    """Reads and writes the CSV the PlayShelf site consumes."""

    @abstractmethod
    def read(self, path):
        """Returns (LibraryData, [SkippedRow]). Raises ImportFormatError."""

    @abstractmethod
    def write(self, path, videos):
        """Writes the videos; returns how many rows were written."""
