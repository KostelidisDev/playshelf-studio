"""Rules for what a valid game title and video look like."""

from ..utils.dates import format_published_at, parse_datetime
from ..utils.text import clean
from ..utils.youtube import parse_video_id
from .errors import ValidationError
from .models import Video

# YouTube caps titles at 100 characters; leave room for edited ones.
MAX_VIDEO_TITLE_LENGTH = 200
MAX_GAME_TITLE_LENGTH = 150


def validate_game_title(title):
    title = clean(title)
    if not title:
        raise ValidationError("Game title is required.")
    if len(title) > MAX_GAME_TITLE_LENGTH:
        raise ValidationError(f"Game title is too long (max {MAX_GAME_TITLE_LENGTH} characters).")
    return title


def validate_video_id(text):
    video_id = parse_video_id(text)
    if not video_id:
        raise ValidationError("Video ID must be an 11-character YouTube id or a YouTube video URL.")
    return video_id


def validate_published_at(text):
    if not (text or "").strip():
        raise ValidationError("Published date is required.")
    value = parse_datetime(text)
    if value is None:
        raise ValidationError(f"'{text.strip()}' isn't a valid date, e.g. 2024-05-09T10:30:30Z.")
    return format_published_at(value)


def validate_video_title(text):
    title = clean(text)
    if not title:
        raise ValidationError("Title is required.")
    if len(title) > MAX_VIDEO_TITLE_LENGTH:
        raise ValidationError(f"Title is too long (max {MAX_VIDEO_TITLE_LENGTH} characters).")
    return title


def validate_video(video):
    """Returns a cleaned copy of `video` (game title not checked against the
    games list; the Library does that)."""
    game = clean(video.game_title)
    return Video(
        video_id=validate_video_id(video.video_id),
        title=validate_video_title(video.title),
        published_at=validate_published_at(video.published_at),
        game_title=validate_game_title(game) if game else "",
    )
