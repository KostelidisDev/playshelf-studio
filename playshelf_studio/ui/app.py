"""Main window: toolbar, games sidebar | video list | details pane, menus,
first-run screen, import/export, undo/redo.

The App gets its Library and Settings from outside (see playshelf_studio.main)
and never touches files directly; every data change goes through the Library.
"""

import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk

from .. import __version__
from ..config import APP_NAME
from ..core import ConflictError, PlayShelfError
from ..storage import read_first_column
from ..utils.youtube import parse_video_id
from .detail import VideoDetail
from .dialogs import GameDialog
from .platform import MOD, MOD_LABEL, open_folder
from .sidebar import ALL, NO_GAME, GameSidebar
from .video_list import VideoList
from .welcome import WelcomeScreen
from .widgets import SearchBar

log = logging.getLogger(__name__)

CSV_TYPES = [("CSV files", "*.csv"), ("All files", "*.*")]
ERROR_COLOR = "#d64545"
WARN_COLOR = "#d9822b"
SIDEBAR_WIDTH = 220
DETAIL_WIDTH = 400
TEXT_INPUTS = (tk.Entry, ttk.Entry, ttk.Combobox, ttk.Spinbox, tk.Text)


def setup_style(root):
    style = ttk.Style(root)
    if sys.platform.startswith("linux") and "clam" in style.theme_names():
        style.theme_use("clam")  # Tk's "default" theme looks dated
    # Tk's default font already matches each OS's normal UI text size.
    base = font.nametofont("TkDefaultFont").actual()
    size = base["size"]
    # Tkinter deletes a named font when its Font object is garbage-collected; keep them.
    root.fonts = [
        font.Font(root, name="ListFont", family=base["family"], size=size),
        font.Font(root, name="HeaderFont", family=base["family"], size=size, weight="bold"),
        font.Font(root, name="TitleFont", family=base["family"], size=round(size * 1.6), weight="bold"),
    ]

    style.configure("TLabel", font="ListFont")
    style.configure("Header.TLabel", font="HeaderFont")
    style.configure("Title.TLabel", font="TitleFont")
    style.configure("Muted.TLabel", foreground="gray")
    style.configure("Error.TLabel", foreground=ERROR_COLOR)
    style.configure("Warn.TLabel", foreground=WARN_COLOR)
    style.configure("Treeview", font="ListFont", rowheight=int(root.fonts[0].metrics("linespace") * 1.5))
    style.configure("Treeview.Heading", font="ListFont")


class App(tk.Tk):
    def __init__(self, library, settings):
        super().__init__()
        self.library = library
        self.settings = settings
        self._syncing = False  # set while the app itself changes the list selection
        self.title(APP_NAME)
        self.geometry("1200x720")
        self.minsize(900, 480)
        setup_style(self)

        self._build_menu()
        self.main = ttk.Frame(self)
        self._build_toolbar(self.main)
        panes = ttk.Panedwindow(self.main, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self.sidebar = GameSidebar(panes, self)
        self.videos = VideoList(panes, self)
        self.detail = VideoDetail(panes, self)
        panes.add(self.sidebar, weight=0)
        panes.add(self.videos, weight=1)
        panes.add(self.detail, weight=0)
        self.panes = panes

        self.status = ttk.Label(self, padding=(10, 3), style="Muted.TLabel")
        self.status.pack(side="bottom", fill="x")
        ttk.Separator(self).pack(side="bottom", fill="x")
        self.welcome = None

        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.after(50, self._startup)

    # ---------- Layout ----------

    def _build_toolbar(self, parent):
        bar = ttk.Frame(parent, padding=(8, 8, 8, 4))
        bar.pack(fill="x")
        ttk.Button(bar, text="+ Add video", command=self.add_video).pack(side="left")
        self.search = SearchBar(bar, self.on_filter_changed, placeholder=f"Search videos ({MOD_LABEL}+F)")
        self.search.pack(side="left", fill="x", expand=True, padx=(12, 12))
        self.export_button = ttk.Button(bar, text="Export CSV", default="active", command=self.export)
        self.export_button.pack(side="right")
        self.export_state = ttk.Label(bar)
        self.export_state.pack(side="right", padx=(0, 8))
        ttk.Separator(parent).pack(fill="x")

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Export site CSV", accelerator=f"{MOD_LABEL}+E", command=self.export)
        file_menu.add_command(label="Export site CSV as…", command=self.export_as)
        file_menu.add_separator()
        file_menu.add_command(label="Import site CSV (replace all data)…", command=self.import_site_csv)
        file_menu.add_command(label="Import games list…", command=self.import_games)
        file_menu.add_separator()
        file_menu.add_command(label="Reload data", accelerator=f"{MOD_LABEL}+R", command=self.reload)
        file_menu.add_command(label="Open data folder", command=lambda: open_folder(self.library.location))
        file_menu.add_separator()
        file_menu.add_command(label="Quit", accelerator=f"{MOD_LABEL}+Q", command=self.quit_app)
        menubar.add_cascade(label="File", menu=file_menu)

        self.edit_menu = tk.Menu(menubar, tearoff=False)
        self.edit_menu.add_command(label="Undo", accelerator=f"{MOD_LABEL}+Z", command=self.undo)
        redo = "Shift+Cmd+Z" if sys.platform == "darwin" else "Ctrl+Y"
        self.edit_menu.add_command(label="Redo", accelerator=redo, command=self.redo)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Add video", accelerator=f"{MOD_LABEL}+N", command=self.add_video)
        self.edit_menu.add_command(label="New game…", accelerator=f"{MOD_LABEL}+G", command=self.add_game)
        self.edit_menu.add_command(label="Save video", accelerator=f"{MOD_LABEL}+S", command=self.detail_save)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Find", accelerator=f"{MOD_LABEL}+F", command=self.search_focus)
        menubar.add_cascade(label="Edit", menu=self.edit_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label=f"About {APP_NAME}", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menubar)
        if sys.platform == "darwin":
            # The application menu's "About" item; without this Tk shows the
            # standard macOS panel, which only knows the bundle's Info.plist.
            self.createcommand("tkAboutDialog", self._about)
            self.createcommand("::tk::mac::Quit", self.quit_app)  # app menu Quit / Cmd+Q

        shortcuts = {
            "e": self.export,
            "q": self.quit_app,
            "r": self.reload,
            "n": self.add_video,
            "g": self.add_game,
            "s": self.detail_save,
            "f": self.search_focus,
            "z": self._undo_key,
            "Z": self._redo_key,
            "Shift-z": self._redo_key,
            "Shift-Z": self._redo_key,
        }
        if sys.platform != "darwin":
            shortcuts["y"] = self._redo_key
        for key, action in shortcuts.items():
            # Only when the main window has focus, not inside an open dialog.
            self.bind(f"<{MOD}-{key}>", lambda _e, a=action: (a(), "break")[1])

    # ---------- Startup ----------

    def _startup(self):
        if self.library.exists():
            self.show_main()
            self.reload()
        else:
            self.welcome = WelcomeScreen(self, self._welcome_import, self._welcome_empty, self.library.location)
            self.welcome.pack(fill="both", expand=True)
            self.welcome.import_button.focus_set()

    def show_main(self):
        if self.welcome is not None:
            self.welcome.destroy()
            self.welcome = None
        self.main.pack(fill="both", expand=True)
        self.update_idletasks()
        width = self.panes.winfo_width()
        self.panes.sashpos(0, SIDEBAR_WIDTH)
        self.panes.sashpos(1, max(width - DETAIL_WIDTH, SIDEBAR_WIDTH + 300))

    def _welcome_import(self):
        if self.import_site_csv(confirm=False):
            self.show_main()
            self.refresh()

    def _welcome_empty(self):
        ok, _ = self.run(self.library.initialize_empty)
        if ok:
            self.show_main()
            self.refresh()
            self.set_status("Started an empty library. Add your first video with “+ Add video”.")

    def quit_app(self):
        if self.welcome is None and not self.detail.commit_pending():
            return
        self.destroy()

    # ---------- Error handling ----------

    def run(self, action, *args):
        """Runs a Library action, showing expected failures to the user.
        Returns (ok, result)."""
        try:
            return True, action(*args)
        except ConflictError:
            self.handle_conflict()
        except PlayShelfError as e:
            messagebox.showerror("Error", str(e), parent=self)
        return False, None

    def handle_conflict(self):
        log.warning("Save refused: data files changed on disk")
        messagebox.showwarning(
            "Data changed elsewhere",
            "The data files were changed outside this window (another copy of "
            f"{APP_NAME}, or another program) since they were loaded.\n\n"
            "Your last change was NOT saved. The data will now be reloaded; "
            "please make the change again.",
            parent=self,
        )
        self.detail.show_empty()
        self.reload(ask=False)

    def report_callback_exception(self, exc, value, tb):
        if isinstance(value, ConflictError):
            self.handle_conflict()
            return
        if isinstance(value, PlayShelfError):
            messagebox.showerror("Error", str(value), parent=self)
            return
        log.error("Unexpected error", exc_info=(exc, value, tb))
        messagebox.showerror(
            "Unexpected error",
            f"{exc.__name__}: {value}\n\nDetails were written to the log in the data folder.",
            parent=self,
        )

    # ---------- Refreshing ----------

    def refresh(self, select_video=None, select_game=None):
        """Redraws everything from the Library."""
        if not self.winfo_exists() or self.welcome is not None:
            return
        self._syncing = True
        try:
            self.sidebar.refresh(self.library, select_game=select_game)
            self.detail.set_games(self.library.games)
            kind, game = self.sidebar.selected
            self.videos.refresh(self.library, self.search.query, kind, game, select=select_video)
        finally:
            self.after_idle(self._end_sync)
        self._sync_detail()
        self._update_menus()
        self._update_export_state()

    def _end_sync(self):
        self._syncing = False

    def _sync_detail(self):
        """Shows the list's selection in the details pane, unless the pane is
        busy with a new video or holds edits to a video the list no longer shows."""
        ids = self.videos.selected_ids
        if ids == self.detail.ids:
            if self.detail.mode == "edit":
                video = self.library.find_video(ids[0])
                if video is None:
                    self.detail.show_empty()
                elif not self.detail.dirty and video != self.detail.video:
                    self.detail.load_video(video)  # changed by undo/redo
            elif self.detail.mode == "multi":
                self.detail.show_for([v for v in map(self.library.find_video, ids) if v])
            return
        if not ids and self.detail.mode == "new":
            return
        if self.detail.dirty:
            return  # keep the edits on screen; they'll be saved or asked about later
        self.detail.show_for([v for v in map(self.library.find_video, ids) if v])

    def on_selection_changed(self):
        if self._syncing:
            return
        ids = self.videos.selected_ids
        if ids == self.detail.ids:
            return
        if not ids and self.detail.mode == "new":
            return
        if not self.detail.commit_pending():
            self._syncing = True
            self.videos.select(self.detail.ids)  # stay on the video being edited
            self.after_idle(self._end_sync)
            return
        # The save may have refreshed the list; read the selection again.
        self.detail.show_for([v for v in map(self.library.find_video, self.videos.selected_ids) if v])

    def on_filter_changed(self):
        if self._syncing:
            return
        kind, game = self.sidebar.selected
        self.videos.refresh(self.library, self.search.query, kind, game)
        self._sync_detail()

    def _update_menus(self):
        undo, redo = self.library.undo_label, self.library.redo_label
        self.edit_menu.entryconfigure(0, label=f"Undo {undo.capitalize()}" if undo else "Undo",
                                      state="normal" if undo else "disabled")
        self.edit_menu.entryconfigure(1, label=f"Redo {redo.capitalize()}" if redo else "Redo",
                                      state="normal" if redo else "disabled")

    def _update_export_state(self):
        exported = self.settings.get("export_fingerprint")
        if not self.library.videos and not exported:
            self.export_state.configure(text="", style="Muted.TLabel")
        elif exported == self.library.export_fingerprint():
            self.export_state.configure(text="✓ Site CSV up to date", style="Muted.TLabel")
        elif exported:
            self.export_state.configure(text="● Changes not exported yet", style="Warn.TLabel")
        else:
            self.export_state.configure(text="● Not exported yet", style="Warn.TLabel")

    def set_status(self, text):
        self.status.configure(text=text)

    # ---------- Videos ----------

    def add_video(self):
        if self.welcome is not None or not self.detail.commit_pending():
            return
        _, game = self.sidebar.selected
        video_id = ""
        try:
            candidate = parse_video_id(self.clipboard_get())
            if candidate and self.library.find_video(candidate) is None:
                video_id = candidate
        except tk.TclError:
            pass  # empty or non-text clipboard
        self._syncing = True
        self.videos.select(())
        self.after_idle(self._end_sync)
        self.detail.start_new(default_game=game or "", video_id=video_id)
        if video_id:
            self.set_status("Filled in the YouTube link from the clipboard.")

    def after_video_saved(self, video, created):
        self.set_status(f"{'Added' if created else 'Saved'} “{video.title}”.")
        if created:
            kind, game = self.sidebar.selected
            if kind == NO_GAME and video.game_title or kind == "game" and video.game_title != game:
                self.sidebar.select(ALL)  # make sure the new video is visible
            self.search.clear()
        self.refresh(select_video=video.video_id)

    def on_new_cancelled(self):
        self.videos.focus()

    def detail_save(self):
        if self.welcome is None:
            self.detail.save()

    def delete_selected(self):
        ids = self.detail.ids if self.detail.mode in ("edit", "multi") else ()
        if not ids:
            return
        videos = [v for v in map(self.library.find_video, ids) if v]
        ok, _ = self.run(self.library.delete_videos, ids)
        if ok:
            what = f"“{videos[0].title}”" if len(videos) == 1 else f"{len(videos)} videos"
            self.detail.show_empty()
            self.refresh()
            self.set_status(f"Deleted {what}. Undo with {MOD_LABEL}+Z.")

    def set_game(self, video_ids, game):
        if game and self.library.find_game(game) is None:
            if not messagebox.askyesno("New game", f"“{game}” isn't in the games list.\n\nAdd it?", parent=self):
                return
            ok, game = self.run(self.library.add_game, game)
            if not ok:
                return
        ok, game = self.run(self.library.set_game, video_ids, game)
        if ok:
            self.refresh()
            target = f"“{game}”" if game else "no game"
            self.set_status(f"Set {len(video_ids)} videos to {target}.")

    # ---------- Games ----------

    def add_game(self):
        if self.welcome is not None:
            return
        dialog = GameDialog(self)
        if dialog.result:
            self.refresh(select_game=dialog.result)
            self.set_status(f"Added the game “{dialog.result}”.")

    def rename_game(self, title):
        if not self.detail.commit_pending():
            return
        dialog = GameDialog(self, original=title)
        if dialog.result:
            self.refresh(select_game=dialog.result)
            self.set_status(f"Renamed “{title}” to “{dialog.result}”.")

    def delete_game(self, title):
        if not self.detail.commit_pending():
            return
        count = self.library.video_count(title)
        ok, _ = self.run(self.library.delete_game, title)
        if ok:
            self.refresh()
            extra = f" Its {count} video(s) now have no game." if count else ""
            self.set_status(f"Deleted the game “{title}”.{extra} Undo with {MOD_LABEL}+Z.")

    # ---------- Undo / redo ----------

    def _undo_key(self):
        if not isinstance(self.focus_get(), TEXT_INPUTS):
            self.undo()

    def _redo_key(self):
        if not isinstance(self.focus_get(), TEXT_INPUTS):
            self.redo()

    def undo(self):
        if self.detail.dirty:
            self.detail.revert()
            self.set_status("Discarded your unsaved edits.")
            return
        ok, label = self.run(self.library.undo)
        if ok and label:
            self.refresh()
            self.set_status(f"Undid: {label}.")

    def redo(self):
        if self.detail.dirty:
            return
        ok, label = self.run(self.library.redo)
        if ok and label:
            self.refresh()
            self.set_status(f"Redid: {label}.")

    # ---------- File actions ----------

    def search_focus(self):
        if self.welcome is None:
            self.search.focus()

    def reload(self, ask=True):
        if ask and not self.detail.commit_pending():
            return
        ok, skipped = self.run(self.library.load)
        if not ok:
            return
        self.refresh()
        if skipped:
            lines = "\n".join(f"  line {s.line}: {s.reason}" for s in skipped[:10])
            messagebox.showwarning(
                "Some rows were skipped",
                f"{len(skipped)} row(s) in the data files are invalid and were skipped "
                f"(they'll be removed on the next save):\n\n{lines}",
                parent=self,
            )
        self.set_status(f"Loaded {len(self.library.videos)} videos and {len(self.library.games)} games.")

    def import_site_csv(self, confirm=True):
        if confirm and not self.detail.commit_pending():
            return False
        if confirm and not messagebox.askyesno(
            "Import site CSV",
            "This replaces ALL local games and videos with the contents of the chosen CSV.\n\n"
            "The current data is backed up first (data folder → backups), and you can "
            f"undo it with {MOD_LABEL}+Z.\n\nContinue?",
            icon="warning", parent=self,
        ):
            return False
        path = filedialog.askopenfilename(
            parent=self, title="Choose PlayShelf's videos.csv", filetypes=CSV_TYPES,
            initialdir=self.settings.get_existing_dir("import_dir"),
        )
        if not path:
            return False
        ok, report = self.run(self.library.import_site_csv, path)
        if not ok:
            return False
        # The imported file is what the site has, so it counts as exported there.
        self.settings.update({
            "import_dir": str(Path(path).parent),
            "export_path": path,
            "export_fingerprint": self.library.export_fingerprint(),
        })
        self.detail.show_empty()
        self.refresh()
        self.set_status(f"Imported {report.videos} videos and {report.games} games.")
        if report.skipped:
            messagebox.showwarning("Imported with warnings", report.summary(), parent=self)
        return True

    def import_games(self):
        path = filedialog.askopenfilename(
            parent=self, title="Choose a games list (one title per row)", filetypes=CSV_TYPES,
            initialdir=self.settings.get_existing_dir("import_dir"),
        )
        if not path:
            return
        ok, titles = self.run(read_first_column, path)
        if not ok:
            return
        ok, added = self.run(self.library.add_games, titles)
        if not ok:
            return
        self.settings.set("import_dir", str(Path(path).parent))
        self.refresh()
        self.set_status(f"Added {added} new game(s).")

    def export(self):
        """Exports to the last used file without asking; the first time, asks where."""
        last = self.settings.get("export_path")
        if isinstance(last, str) and last and Path(last).parent.is_dir():
            self._export_to(last)
        else:
            self.export_as()

    def export_as(self):
        last = self.settings.get("export_path")
        last = Path(last) if isinstance(last, str) and last else None
        path = filedialog.asksaveasfilename(
            parent=self, title="Export site CSV", defaultextension=".csv", filetypes=CSV_TYPES,
            initialdir=str(last.parent) if last and last.parent.is_dir() else str(Path.home()),
            initialfile=last.name if last else "videos.csv",
        )
        if path:
            self._export_to(path)

    def _export_to(self, path):
        if self.welcome is not None or not self.detail.commit_pending():
            return
        if Path(path).resolve().parent == Path(self.library.location).resolve():
            messagebox.showerror(
                "Choose another folder",
                "That's the app's own data folder; exporting there would overwrite its data files.\n\n"
                "Choose another folder, e.g. where PlayShelf picks up its catalog.",
                parent=self,
            )
            return
        ok, count = self.run(self.library.export_site_csv, path)
        if not ok:
            return
        self.settings.update({"export_path": path, "export_fingerprint": self.library.export_fingerprint()})
        log.info("Exported %s videos to %s", count, path)
        self._update_export_state()
        self.set_status(f"Exported {count} videos to {path}")

    # ---------- Help ----------

    def _about(self):
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME} {__version__}\n\n"
            "The catalog editor for PlayShelf: a hand-picked collection of YouTube "
            "videos, grouped by game, from any creators.\n\n"
            f"Data folder:\n{self.library.location}",
            parent=self,
        )
