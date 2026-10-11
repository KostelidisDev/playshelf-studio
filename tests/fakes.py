"""Test doubles for the core interfaces."""

from playshelf_studio.core import LibraryData, LibraryRepository


class MemoryRepository(LibraryRepository):
    def __init__(self, data=None):
        self.data = data
        self.saves = 0
        self.backups = []
        self.fail_with = None  # exception to raise on the next save

    @property
    def location(self):
        return "memory"

    def exists(self):
        return self.data is not None

    def load(self):
        return self.data or LibraryData(), []

    def save(self, data):
        if self.fail_with:
            error, self.fail_with = self.fail_with, None
            raise error
        self.data = data
        self.saves += 1

    def backup(self, reason):
        self.backups.append((reason, self.data))
        return reason
