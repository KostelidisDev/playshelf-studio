"""Exceptions raised by the core and storage layers.

The UI shows ValidationError messages as-is, so they're written for users.
"""


class PlayShelfError(Exception):
    """Base class for every expected, user-facing failure."""


class ValidationError(PlayShelfError, ValueError):
    """A value or change was rejected (missing, duplicate, malformed...)."""


class ImportFormatError(ValidationError):
    """A file to import isn't in the expected format."""


class ConflictError(PlayShelfError):
    """The data files changed on disk since they were read (another copy of
    the app, or a program like Excel), so saving would overwrite that change."""


class StorageError(PlayShelfError):
    """The data files couldn't be read or written."""
