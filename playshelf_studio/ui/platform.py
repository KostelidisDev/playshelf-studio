"""OS-specific bits: shortcut modifier names, opening folders and URLs."""

import os
import subprocess
import sys
import webbrowser

from ..utils.youtube import watch_url

MOD = "Command" if sys.platform == "darwin" else "Control"
MOD_LABEL = "Cmd" if sys.platform == "darwin" else "Ctrl"


def open_folder(path):
    path = os.fspath(path)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - a local folder we created
    else:
        # List form, no shell: the path is never interpreted as a command.
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])


def open_video(video_id):
    """Opens a video on YouTube. watch_url() rejects anything but a valid id,
    so a crafted id can't turn into another URL or scheme."""
    webbrowser.open(watch_url(video_id))
