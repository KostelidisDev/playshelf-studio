"""YouTube video ids and URLs."""

import json
import re
import ssl
import urllib.parse
import urllib.request
from functools import cache

from .text import clean

# YouTube video ids are exactly 11 characters from this URL-safe alphabet.
# Everything that builds a URL or a file name from an id relies on this.
VIDEO_ID_RE = re.compile(r"\A[A-Za-z0-9_-]{11}\Z")
_URL_ID_RE = re.compile(
    r"\A(?:https?://)?(?:(?:www|m|music)\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)/"
    r"(?:watch\?(?:.*&)?v=|shorts/|embed/|live/|v/)?([A-Za-z0-9_-]{11})(?:[?&#/].*)?\Z",
    re.IGNORECASE,
)


def is_video_id(text):
    return bool(VIDEO_ID_RE.match(text or ""))


def parse_video_id(text):
    """Accepts a bare id or a youtube.com / youtu.be URL; returns the id or None."""
    text = (text or "").strip()
    if is_video_id(text):
        return text
    match = _URL_ID_RE.match(text)
    return match.group(1) if match else None


def watch_url(video_id):
    if not is_video_id(video_id):
        raise ValueError(f"Not a YouTube video id: {video_id!r}")
    return f"https://www.youtube.com/watch?v={video_id}"


OEMBED_URL = "https://www.youtube.com/oembed?format=json&url="
MAX_OEMBED_BYTES = 64 * 1024


@cache
def _ssl_context():
    """Verifies against certifi's CA bundle when it's installed (it's bundled
    into the built app: a frozen macOS build can't rely on the build machine's
    OpenSSL certificate paths), else the system's."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def fetch_title(video_id, timeout=5):
    """The video's title from YouTube's oEmbed endpoint (no API key needed).

    Blocking; call it off the UI thread. Raises OSError (no network, video
    private or missing...) or ValueError (unexpected response).
    """
    url = OEMBED_URL + urllib.parse.quote(watch_url(video_id), safe="")
    with urllib.request.urlopen(url, timeout=timeout, context=_ssl_context()) as response:  # noqa: S310 - fixed https URL
        body = response.read(MAX_OEMBED_BYTES + 1)
    if len(body) > MAX_OEMBED_BYTES:
        raise ValueError("oEmbed response too large")
    title = json.loads(body).get("title")
    if not isinstance(title, str) or not clean(title):
        raise ValueError("oEmbed response has no title")
    return clean(title)
