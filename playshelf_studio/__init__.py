"""PlayShelf Studio: desktop catalog editor for PlayShelf, a hand-picked
collection of YouTube videos grouped by game.

Layers (each only imports the ones above it):

    utils    text / YouTube id / date helpers
    core     models, validation, Library service, storage interfaces
    storage  CSV implementations of the core interfaces
    config   data folder, settings, logging
    ui       Tkinter GUI
"""

from ._version import __version__

__all__ = ["__version__", "main"]


def main():
    """Composition root: wires storage into the Library and starts the GUI."""
    from .config import Settings, data_dir, setup_logging
    from .core import Library
    from .storage import CsvRepository, SiteCsvFormat
    from .ui import App

    directory = data_dir()
    setup_logging(directory)
    library = Library(CsvRepository(directory), SiteCsvFormat())
    App(library, Settings(directory)).mainloop()
