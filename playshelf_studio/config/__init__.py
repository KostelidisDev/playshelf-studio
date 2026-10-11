"""Configuration: data folder location, settings and logging."""

from .logging_setup import setup_logging
from .paths import APP_NAME, data_dir
from .settings import Settings

__all__ = ["APP_NAME", "Settings", "data_dir", "setup_logging"]
