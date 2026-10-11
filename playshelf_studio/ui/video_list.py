"""Middle pane: the videos matching the search and the sidebar filter."""

from tkinter import ttk

from ..utils.dates import format_local
from ..utils.text import fold, game_key
from .sidebar import ALL, NO_GAME
from .widgets import ScrolledTree


def matches(video, query, kind, game):
    if kind == NO_GAME and video.game_title:
        return False
    if kind not in (ALL, NO_GAME) and game_key(video.game_title) != game_key(game):
        return False
    return not query or query in fold(f"{video.title}\n{video.game_title}\n{video.video_id}")


class VideoList(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=(0, 8))
        self.app = app
        table = ScrolledTree(self, [
            ("date", "Published", 150, False, "published_at"),
            ("title", "Title", 380, True),
            ("game", "Game", 180, False),
        ], hidden=("published_at",), selectmode="extended")
        table.pack(fill="both", expand=True)
        self.tree = table.tree
        self.empty = ttk.Label(self.tree, style="Muted.TLabel", justify="center")

        self.footer = ttk.Label(self, style="Muted.TLabel")
        self.footer.pack(fill="x", pady=(6, 0))

        self.tree.bind("<<TreeviewSelect>>", lambda _e: app.on_selection_changed())
        self.tree.bind("<Double-1>", lambda e: self.tree.identify_row(e.y) and app.detail.focus_title())
        self.tree.bind("<Return>", lambda _e: app.detail.focus_title())
        self.tree.bind("<Delete>", lambda _e: app.delete_selected())
        self.tree.bind("<BackSpace>", lambda _e: app.delete_selected())

    @property
    def selected_ids(self):
        return tuple(self.tree.selection())

    def refresh(self, library, query, kind, game, select=None):
        self.tree.replace_rows(
            (v.video_id, (format_local(v.published_at), v.title, v.game_title, v.published_at))
            for v in library.videos
            if matches(v, query, kind, game)
        )
        if select:
            self.tree.select_and_show(select)
        shown, total = len(self.tree.get_children()), len(library.videos)
        self.footer.configure(text=f"{shown} of {total} videos" if shown != total else f"{total} videos")
        if shown:
            self.empty.place_forget()
        else:
            if not total:
                text = "No videos yet.\nAdd one with “+ Add video”."
            elif query:
                text = "No videos match your search."
            else:
                text = "No videos here."
            self.empty.configure(text=text)
            self.empty.place(relx=0.5, rely=0.35, anchor="center")

    def select(self, video_ids):
        self.tree.selection_set([i for i in video_ids if self.tree.exists(i)])

    def focus(self):
        self.tree.focus_set()
