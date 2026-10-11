"""Converts between CSV rows and Video objects (shared by the local
videos.csv and the site CSV, which use the same columns)."""

from ..core.errors import ImportFormatError, ValidationError
from ..core.models import SkippedRow, Video
from ..core.validation import validate_video

VIDEO_FIELDS = ["video_id", "title", "published_at", "game_title"]


def rows_to_videos(fieldnames, rows, source_name):
    """Returns ([Video], [SkippedRow]); invalid and duplicate rows are skipped."""
    missing = [f for f in VIDEO_FIELDS if f not in fieldnames]
    if missing:
        raise ImportFormatError(f"{source_name} is missing column(s): {', '.join(missing)}.")

    videos, skipped, seen = [], [], set()
    for line, row in rows:
        try:
            video = validate_video(Video(**{f: row.get(f) or "" for f in VIDEO_FIELDS}))
        except ValidationError as e:
            skipped.append(SkippedRow(line, str(e)))
            continue
        if video.video_id in seen:
            skipped.append(SkippedRow(line, f"duplicate video id {video.video_id}"))
            continue
        seen.add(video.video_id)
        videos.append(video)
    return videos, skipped


def video_to_row(video, title=None):
    return {
        "video_id": video.video_id,
        "title": video.title if title is None else title,
        "published_at": video.published_at,
        "game_title": video.game_title,
    }
