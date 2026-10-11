"""Text normalisation for titles coming from users, CSV files and YouTube."""

import re
import unicodedata
from functools import lru_cache

# Bidirectional-override and isolate controls: invisible, and able to make a
# title display as something other than what it contains ("Trojan Source").
_BIDI_CONTROLS = re.compile("[‪-‮⁦-⁩‎‏؜]")

# Characters swapped for look-alikes in the site CSV, so its rows never need
# quoting (some consumers split lines on commas naively).
_SITE_CSV_REPLACEMENTS = {",": ";", '"': "'"}


def clean(text):
    """Single-line, trimmed text without control or bidi-override characters.

    Every kind of whitespace (tabs, newlines, NBSP...) becomes one space.
    """
    text = _BIDI_CONTROLS.sub("", text or "")
    text = "".join(
        " " if ch.isspace() else ch
        for ch in text
        if ch.isspace() or unicodedata.category(ch) not in ("Cc", "Cf") or ch == "‍"
    )
    return " ".join(text.split())


@lru_cache(maxsize=4096)
def game_key(title):
    """Comparison key for game titles: case- and whitespace-insensitive.

    Cached: it's called for every video on each refresh and search keystroke.
    """
    return clean(title).casefold()


def fold(text):
    """Case-insensitive search key."""
    return (text or "").casefold()


def to_site_csv_title(title):
    title = clean(title)
    for old, new in _SITE_CSV_REPLACEMENTS.items():
        title = title.replace(old, new)
    return title
