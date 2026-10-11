"""Plain data types. Immutable: changes produce new objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    published_at: str  # YYYY-MM-DDTHH:MM:SSZ
    game_title: str = ""


@dataclass(frozen=True)
class LibraryData:
    """Everything the app stores: the games list and the videos."""

    games: tuple = ()   # of str
    videos: tuple = ()  # of Video


@dataclass(frozen=True)
class SkippedRow:
    line: int     # 1-based line in the file (header is line 1)
    reason: str


@dataclass(frozen=True)
class ImportReport:
    videos: int
    games: int
    skipped: tuple = ()  # of SkippedRow

    def summary(self, limit=10):
        text = f"Imported {self.videos} videos and {self.games} games."
        if self.skipped:
            lines = [f"  line {s.line}: {s.reason}" for s in self.skipped[:limit]]
            if len(self.skipped) > limit:
                lines.append(f"  … and {len(self.skipped) - limit} more")
            text += f"\n\nSkipped {len(self.skipped)} row(s):\n" + "\n".join(lines)
        return text
