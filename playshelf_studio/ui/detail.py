"""Right pane: edit the selected video, add a new one, or act on several.

Edits stay in the form until saved (Save, Return or Cmd/Ctrl+S). Moving to
another video saves them automatically; a new video that hasn't been added
yet asks first, so a half-typed one is never added by accident.
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ..core import ConflictError, PlayShelfError, Video
from ..core.validation import validate_video
from ..utils.dates import format_local, format_published_at, now_utc, parse_datetime
from ..utils.youtube import fetch_title, parse_video_id
from .datetime_picker import DateTimePicker
from .platform import MOD_LABEL, open_video
from .widgets import GameCombobox

MAX_TABS_OPENED = 5
FETCH_DELAY_MS = 400
FIELD_WIDTH = 34

EMPTY, EDIT, NEW, MULTI = "empty", "edit", "new", "multi"


class VideoDetail(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=(12, 8, 12, 8))
        self.app = app
        self.mode = EMPTY
        self.video = None      # the Video being edited (EDIT)
        self.ids = ()          # ids of the video(s) shown
        self._original = None  # field values as loaded, to detect edits
        self._loading = False
        self._fetch_token = 0
        self._fetch_job = None

        self.placeholder = ttk.Label(
            self, style="Muted.TLabel", justify="center", wraplength=260,
            text=f"Select a video to edit it,\nor add one with “+ Add video” ({MOD_LABEL}+N).",
        )
        self.form = ttk.Frame(self)
        self._build_form(self.form)
        self.multi = ttk.Frame(self)
        self._build_multi(self.multi)
        self.show_empty()

    # ---------- Layout ----------

    def _build_form(self, form):
        form.columnconfigure(0, weight=1)
        self.header = ttk.Label(form, style="Header.TLabel")
        self.header.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.id_var = tk.StringVar()
        self.title_var = tk.StringVar()
        row = self._field(form, 1, "YouTube URL or ID")
        self.id_entry = ttk.Entry(form, textvariable=self.id_var, width=FIELD_WIDTH)
        self.id_entry.grid(row=row, column=0, sticky="ew")
        self.id_hint = ttk.Label(form, style="Muted.TLabel")
        self.id_hint.grid(row=row + 1, column=0, sticky="w")

        row = self._field(form, 4, "Title")
        title_row = ttk.Frame(form)
        title_row.grid(row=row, column=0, sticky="ew")
        ttk.Button(title_row, text="From YouTube", command=lambda: self.fetch_title(overwrite=True),
                   takefocus=False).pack(side="right", padx=(4, 0))
        self.title_entry = ttk.Entry(title_row, textvariable=self.title_var, width=10)
        self.title_entry.pack(side="left", fill="x", expand=True)
        self.fetch_hint = ttk.Label(form, style="Muted.TLabel")
        self.fetch_hint.grid(row=row + 1, column=0, sticky="w")

        row = self._field(form, 7, "Published (UTC)")
        self.published = DateTimePicker(form)
        self.published.grid(row=row, column=0, sticky="ew")
        self.date_hint = ttk.Label(form, style="Muted.TLabel")
        self.date_hint.grid(row=row + 1, column=0, sticky="w")

        row = self._field(form, 10, "Game")
        self.game = GameCombobox(form, width=FIELD_WIDTH)
        self.game.grid(row=row, column=0, sticky="ew")
        self.game_hint = ttk.Label(form, style="Muted.TLabel")
        self.game_hint.grid(row=row + 1, column=0, sticky="w")

        self.error = ttk.Label(form, style="Error.TLabel", justify="left")
        self.error.grid(row=13, column=0, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(form)
        buttons.grid(row=14, column=0, sticky="ew", pady=(10, 0))
        self.save_button = ttk.Button(buttons, text="Save", default="active", command=self.save)
        self.save_button.pack(side="left")
        self.revert_button = ttk.Button(buttons, text="Revert", command=self.revert)
        self.revert_button.pack(side="left", padx=(4, 0))

        self.extra = ttk.Frame(form)
        self.extra.grid(row=15, column=0, sticky="ew", pady=(16, 0))
        ttk.Separator(self.extra).pack(fill="x", pady=(0, 10))
        ttk.Button(self.extra, text="Open on YouTube", command=self.open_youtube).pack(side="left")
        ttk.Button(self.extra, text="Delete", command=self.app.delete_selected).pack(side="right")

        for hint in (self.id_hint, self.fetch_hint, self.date_hint, self.game_hint):
            hint.configure(wraplength=340, justify="left")
        self.error.configure(wraplength=340)
        for var in (self.title_var, self.published.var):
            var.trace_add("write", lambda *_: self._changed())
        self.id_var.trace_add("write", lambda *_: self._id_changed())
        self.game.bind("<<ComboboxSelected>>", lambda _e: self._changed())
        self.game.bind("<KeyRelease>", lambda _e: self._changed(), add="+")
        for widget in (self.id_entry, self.title_entry, self.published.entry, self.game):
            widget.bind("<Return>", lambda _e: self.save())
            widget.bind("<KP_Enter>", lambda _e: self.save())
            widget.bind("<Escape>", lambda _e: self.revert())

    def _field(self, form, row, label):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=(6, 2))
        return row + 1

    def _build_multi(self, frame):
        frame.columnconfigure(0, weight=1)
        self.multi_header = ttk.Label(frame, style="Header.TLabel")
        self.multi_header.grid(row=0, column=0, sticky="w", pady=(0, 10))
        ttk.Label(frame, text="Set game for all of them").grid(row=1, column=0, sticky="w", pady=(6, 2))
        row = ttk.Frame(frame)
        row.grid(row=2, column=0, sticky="ew")
        self.multi_game = GameCombobox(row, width=FIELD_WIDTH - 8)
        self.multi_game.pack(side="left", fill="x", expand=True)
        self.multi_game.bind("<Return>", lambda _e: self._apply_multi_game())
        ttk.Button(row, text="Apply", command=self._apply_multi_game).pack(side="left", padx=(4, 0))
        ttk.Label(frame, text="Leave empty to remove their game.", style="Muted.TLabel").grid(row=3, column=0, sticky="w")

        actions = ttk.Frame(frame)
        actions.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        ttk.Separator(actions).pack(fill="x", pady=(0, 10))
        ttk.Button(actions, text="Open on YouTube", command=self.open_youtube).pack(side="left")
        self.multi_delete = ttk.Button(actions, command=self.app.delete_selected)
        self.multi_delete.pack(side="right")

    def _show(self, frame):
        for child in (self.placeholder, self.form, self.multi):
            child.pack_forget()
        if frame is self.placeholder:
            frame.pack(expand=True)
        else:
            frame.pack(fill="both", expand=True, anchor="n")

    # ---------- What's shown ----------

    def set_games(self, games):
        self.game.set_games(games)
        self.multi_game.set_games(games)

    def show_empty(self):
        self.mode, self.video, self.ids = EMPTY, None, ()
        self._show(self.placeholder)

    def show_for(self, videos):
        """Shows the given videos: none, one (editable) or several."""
        if not videos:
            self.show_empty()
        elif len(videos) == 1:
            self.load_video(videos[0])
        else:
            self.mode, self.video, self.ids = MULTI, None, tuple(v.video_id for v in videos)
            self.multi_header.configure(text=f"{len(videos)} videos selected")
            self.multi_delete.configure(text=f"Delete {len(videos)} videos")
            games = {v.game_title for v in videos}
            self.multi_game.set(games.pop() if len(games) == 1 else "")
            self._show(self.multi)

    def load_video(self, video):
        self.mode, self.video, self.ids = EDIT, video, (video.video_id,)
        self.header.configure(text="Video")
        self._fill(video.video_id, video.title, video.published_at, video.game_title)
        self.extra.grid()
        self._show(self.form)

    def start_new(self, default_game="", video_id=""):
        self.mode, self.video, self.ids = NEW, None, ()
        self.header.configure(text="New video")
        self._fill("", "", format_published_at(now_utc()), default_game)
        self.extra.grid_remove()
        self._show(self.form)
        if video_id:
            self.id_var.set(video_id)  # counts as an edit; triggers the title lookup
            self.title_entry.focus_set()
        else:
            self.id_entry.focus_set()

    def _fill(self, video_id, title, published_at, game):
        self._loading = True
        self._fetch_token += 1  # ignore lookups still running for the previous video
        try:
            self.id_var.set(video_id)
            self.title_var.set(title)
            self.published.var.set(published_at)
            self.game.set(game)
        finally:
            self._loading = False
        self._original = self._values()
        self.error.configure(text="")
        self.fetch_hint.configure(text="")
        self._changed()

    def focus_title(self):
        if self.mode in (EDIT, NEW):
            self.title_entry.focus_set()
            self.title_entry.select_range(0, "end")

    # ---------- Edits ----------

    def _values(self):
        return (self.id_var.get().strip(), self.title_var.get().strip(),
                self.published.var.get().strip(), self.game.value)

    @property
    def dirty(self):
        return self.mode in (EDIT, NEW) and self._values() != self._original

    def _changed(self):
        if self._loading:
            return
        dirty = self.dirty
        base = "New video" if self.mode == NEW else "Video"
        self.header.configure(text=f"{base} •" if dirty and self.mode == EDIT else base)
        self.save_button.state(["!disabled"] if dirty else ["disabled"])
        self.revert_button.state(["!disabled"] if dirty or self.mode == NEW else ["disabled"])
        self.error.configure(text="")

        published = self.published.var.get()
        value = parse_datetime(published)
        if value:
            self.date_hint.configure(text=f"{format_local(published)} your time", style="Muted.TLabel")
        elif published.strip():
            self.date_hint.configure(text="Not a valid date, e.g. 2024-05-09 or 2024-05-09T10:30:30Z", style="Error.TLabel")
        else:
            self.date_hint.configure(text="Type a date or use Pick…", style="Muted.TLabel")

        game = self.game.value
        new_game = game and self.app.library.find_game(game) is None
        self.game_hint.configure(text="New game: it'll be added to the games list." if new_game else "")

    def _id_changed(self):
        if self._loading:
            return
        video_id = parse_video_id(self.id_var.get())
        existing = self.app.library.find_video(video_id) if video_id else None
        if existing is not None and existing.video_id not in self.ids:
            self.id_hint.configure(text="This video is already in the library.", style="Error.TLabel")
        elif self.id_var.get().strip() and not video_id:
            self.id_hint.configure(text="Not a YouTube video URL or ID yet.", style="Muted.TLabel")
        else:
            self.id_hint.configure(text="")
        if self._fetch_job:
            self.after_cancel(self._fetch_job)
            self._fetch_job = None
        if video_id and not self.title_var.get().strip():
            self._fetch_job = self.after(FETCH_DELAY_MS, lambda: self.fetch_title(overwrite=False))
        self._changed()

    def save(self):
        """Saves the form. Returns True on success (or nothing to save)."""
        if self.mode not in (EDIT, NEW) or not self.dirty:
            return True
        library = self.app.library
        video_id, title, published_at, game = self._values()
        video = Video(video_id, title, published_at, game)
        try:
            if game and library.find_game(game) is None:
                validate_video(Video(video_id, title, published_at, ""))  # don't add a game for a bad video
                library.add_game(game)
            if self.mode == NEW:
                saved = library.add_video(video)
            else:
                saved = library.update_video(self.video.video_id, video)
        except ConflictError:
            self.app.handle_conflict()
            return False
        except PlayShelfError as e:
            self.error.configure(text=str(e))
            self.bell()
            return False
        created = self.mode == NEW
        self.load_video(saved)
        self.app.after_video_saved(saved, created)
        return True

    def revert(self):
        if self.mode == EDIT:
            self.load_video(self.video)
        elif self.mode == NEW:
            self.show_empty()
            self.app.on_new_cancelled()

    def commit_pending(self):
        """Called before showing something else. Saves edits to an existing
        video; asks about an unsaved new one. Returns False to stay put."""
        if not self.dirty:
            return True
        if self.mode == NEW:
            answer = messagebox.askyesnocancel(
                "Add this video?", "You haven't added the new video yet.\n\nAdd it now?", parent=self.app)
            if answer is None:
                return False
            if not answer:
                self.show_empty()
                return True
        if self.save():
            return True
        if messagebox.askyesno(
            "Can't save this video",
            f"{self.error.cget('text')}\n\nDiscard your changes to it?",
            icon="warning", parent=self.app,
        ):
            self.show_empty()
            return True
        return False

    # ---------- Title lookup ----------

    def fetch_title(self, overwrite):
        """Fills in the title from YouTube on a worker thread (Tk isn't
        thread-safe, so the result is picked up by polling with after())."""
        self._fetch_job = None
        video_id = parse_video_id(self.id_var.get())
        if not video_id:
            self.fetch_hint.configure(text="Enter a YouTube URL or ID first.", style="Error.TLabel")
            return
        self._fetch_token += 1
        token = self._fetch_token
        self.fetch_hint.configure(text="Getting the title from YouTube…", style="Muted.TLabel")
        result = {}

        def work():
            try:
                result["title"] = fetch_title(video_id)
            except (OSError, ValueError):
                result["title"] = None

        thread = threading.Thread(target=work, daemon=True)
        thread.start()

        def poll():
            if thread.is_alive():
                self.after(100, poll)
                return
            if token != self._fetch_token or not self.winfo_exists():
                return  # another video is shown by now
            title = result.get("title")
            if not title:
                self.fetch_hint.configure(text="Couldn't get the title (offline, or the video is private).",
                                          style="Error.TLabel")
            elif overwrite or not self.title_var.get().strip():
                self.title_var.set(title)
                self.fetch_hint.configure(text="Title filled in from YouTube.", style="Muted.TLabel")
            else:
                self.fetch_hint.configure(text="")

        self.after(100, poll)

    # ---------- Actions ----------

    def open_youtube(self):
        for video_id in self.ids[:MAX_TABS_OPENED]:
            open_video(video_id)

    def _apply_multi_game(self):
        self.app.set_game(self.ids, self.multi_game.value)
