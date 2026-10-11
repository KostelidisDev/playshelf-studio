"""The videos.csv the PlayShelf site serves: video_id, title, published_at, game_title.

These columns are the contract with PlayShelf; changing them breaks the site.
"""

from pathlib import Path

from ..core.interfaces import SiteFormat
from ..core.models import LibraryData
from ..utils.text import to_site_csv_title
from .csv_files import read_rows, write_rows
from .video_rows import VIDEO_FIELDS, rows_to_videos, video_to_row


class SiteCsvFormat(SiteFormat):
    def read(self, path):
        fieldnames, rows = read_rows(path)
        videos, skipped = rows_to_videos(fieldnames, rows, Path(path).name)
        games = [v.game_title for v in videos if v.game_title]
        return LibraryData(games=tuple(games), videos=tuple(videos)), skipped

    def write(self, path, videos):
        ordered = sorted(videos, key=lambda v: v.published_at, reverse=True)
        write_rows(path, VIDEO_FIELDS, [video_to_row(v, title=to_site_csv_title(v.title)) for v in ordered])
        return len(ordered)
