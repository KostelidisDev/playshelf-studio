"""Logs to <data folder>/logs/playshelf-studio.log (rotated) and to stderr."""

import logging
from logging.handlers import RotatingFileHandler

from .paths import log_dir

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(base_dir, level=logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)
    handlers = [logging.StreamHandler()]
    try:
        directory = log_dir(base_dir)
        directory.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(directory / "playshelf-studio.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    except OSError:
        pass  # a read-only data folder shouldn't stop the app from starting
    for handler in handlers:
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
