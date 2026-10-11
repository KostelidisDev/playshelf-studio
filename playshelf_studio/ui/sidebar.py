"""Left pane: the games list, which doubles as the videos filter."""

import sys
import tkinter as tk
from tkinter import ttk

from ..utils.text import game_key

ALL = "all"
NO_GAME = "none"
GAME_PREFIX = "game:"
# Secondary click: Button-2 on macOS (plus Control-click), Button-3 elsewhere.
CONTEXT_EVENTS = ("<Button-2>", "<Control-Button-1>") if sys.platform == "darwin" else ("<Button-3>",)


class GameSidebar(ttk.Frame):
    """Rows: All videos, No game, then every game with its video count.

    The app is told about selection changes through `on_change`; game
    actions (add, rename, delete) go back to the app as callbacks.
    """

    def __init__(self, master, app):
        super().__init__(master, padding=(8, 8, 0, 8))
        self.app = app
        self._games = {}  # iid -> title
        self._silent = False

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="Games", style="Header.TLabel").pack(side="left")
        ttk.Button(header, text="+", width=2, command=app.add_game, takefocus=False).pack(side="right")

        box = ttk.Frame(self)
        box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(box, columns=("count",), show="tree", selectmode="browse")
        self.tree.column("#0", width=150, stretch=True)
        self.tree.column("count", width=44, stretch=False, anchor="e")
        self.tree.tag_configure("special", font="HeaderFont")
        self.tree.tag_configure("game", font="ListFont")
        self.tree.tag_configure("unused", foreground="gray")
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self._rename(self.tree.identify_row(e.y)))
        self.tree.bind("<Return>", lambda _e: self._rename(self.tree.focus()))
        self.tree.bind("<Delete>", lambda _e: self._delete(self.tree.focus()))
        self.tree.bind("<BackSpace>", lambda _e: self._delete(self.tree.focus()))
        for event in CONTEXT_EVENTS:
            self.tree.bind(event, self._context_menu)

        self.menu = tk.Menu(self, tearoff=False)
        self._menu_item = None
        self.menu.add_command(label="Rename…", command=lambda: self._rename(self._menu_item))
        self.menu.add_command(label="Delete", command=lambda: self._delete(self._menu_item))
        self.menu.add_separator()
        self.menu.add_command(label="New game…", command=app.add_game)

    @property
    def selected(self):
        """(ALL, None), (NO_GAME, None) or ("game", title)."""
        iid = (self.tree.selection() or (ALL,))[0]
        if iid in self._games:
            return "game", self._games[iid]
        return (iid, None) if iid in (ALL, NO_GAME) else (ALL, None)

    def refresh(self, library, select_game=None):
        """Rebuilds the rows, keeping the selection (by title) unless told otherwise."""
        kind, current = self.selected
        target = game_key(select_game) if select_game else (game_key(current) if current else kind)
        counts = library.game_counts()
        no_game = sum(1 for v in library.videos if not v.game_title)

        self._silent = True
        try:
            self.tree.delete(*self.tree.get_children())
            self._games.clear()
            self.tree.insert("", "end", iid=ALL, text="All videos", values=(len(library.videos),), tags=("special",))
            self.tree.insert("", "end", iid=NO_GAME, text="No game", values=(no_game,), tags=("special",))
            selected = ALL if target == ALL else NO_GAME if target == NO_GAME else None
            for index, game in enumerate(library.games):
                iid = f"{GAME_PREFIX}{index}"
                count = counts.get(game_key(game), 0)
                self.tree.insert("", "end", iid=iid, text=game, values=(count,), tags=("game",) if count else ("game", "unused"))
                self._games[iid] = game
                if game_key(game) == target:
                    selected = iid
            self.tree.selection_set(selected or ALL)
            self.tree.focus(selected or ALL)
            self.tree.see(selected or ALL)
        finally:
            self.after_idle(self._unsilence)

    def select(self, kind, title=None):
        iid = kind if kind in (ALL, NO_GAME) else next(
            (i for i, g in self._games.items() if game_key(g) == game_key(title)), ALL)
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def _unsilence(self):
        self._silent = False

    def _on_select(self, _event):
        if not self._silent:
            self.app.on_filter_changed()

    def _context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        is_game = iid in self._games
        if iid:
            self.tree.selection_set(iid)
        self._menu_item = iid
        for index in (0, 1):
            self.menu.entryconfigure(index, state="normal" if is_game else "disabled")
        self.menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _rename(self, iid):
        if iid in self._games:
            self.app.rename_game(self._games[iid])

    def _delete(self, iid):
        if iid in self._games:
            self.app.delete_game(self._games[iid])
