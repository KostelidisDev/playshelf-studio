"""Reusable Tk widgets: sortable table, search bar, filtering game combobox."""

import tkinter as tk
from tkinter import ttk

from ..utils.text import clean, fold

SORT_ARROWS = {False: " ▲", True: " ▼"}


class SortableTree(ttk.Treeview):
    """Treeview whose column headings sort the rows when clicked.

    `columns` is a list of (key, label, width, stretch[, sort_key]); clicking
    a column sorts by the column named `sort_key` (default: itself), which
    can be one of the `hidden` columns, e.g. a raw date behind a pretty one.
    """

    def __init__(self, master, columns, hidden=(), **kwargs):
        keys = [c[0] for c in columns]
        super().__init__(master, columns=keys + list(hidden), displaycolumns=keys, show="headings", **kwargs)
        self._labels = {}
        self._sort_keys = {}
        self._sort_column = None
        self._sort_reverse = False
        for key, label, width, stretch, *sort_key in columns:
            self._labels[key] = label
            self._sort_keys[key] = sort_key[0] if sort_key else key
            self.heading(key, text=label, anchor="w", command=lambda k=key: self.sort_by(k))
            self.column(key, width=width, minwidth=60, stretch=stretch, anchor="w")

    def sort_by(self, column):
        self._sort_reverse = not self._sort_reverse if self._sort_column == column else False
        self._sort_column = column
        for key, label in self._labels.items():
            self.heading(key, text=label + (SORT_ARROWS[self._sort_reverse] if key == column else ""))
        self.apply_sort()

    def apply_sort(self):
        if self._sort_column is None:
            return
        column = self._sort_keys[self._sort_column]

        def key(item):
            value = self.set(item, column)
            return (0, int(value), "") if value.isdigit() else (1, 0, fold(value))

        items = sorted(self.get_children(""), key=key, reverse=self._sort_reverse)
        for index, item in enumerate(items):
            self.move(item, "", index)

    def replace_rows(self, rows):
        """rows: iterable of (iid, values). Keeps the selection where possible."""
        selected = self.selection()
        self.delete(*self.get_children())
        for iid, values in rows:
            self.insert("", "end", iid=iid, values=values)
        self.apply_sort()
        keep = [i for i in selected if self.exists(i)]
        if keep:
            self.selection_set(keep)

    def select_and_show(self, iid):
        if iid is not None and self.exists(iid):
            self.selection_set(iid)
            self.focus(iid)
            self.see(iid)


class ScrolledTree(ttk.Frame):
    """A SortableTree with a vertical scrollbar."""

    def __init__(self, master, columns, **kwargs):
        super().__init__(master)
        self.tree = SortableTree(self, columns, **kwargs)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")


class SearchBar(ttk.Frame):
    """Search entry with a placeholder (shown while empty) and a clear button."""

    def __init__(self, master, on_change, placeholder="Search"):
        super().__init__(master)
        self.var = tk.StringVar()
        self.var.trace_add("write", lambda *_: on_change())
        self.entry = ttk.Entry(self, textvariable=self.var, width=30)
        self.entry.pack(side="left", fill="x", expand=True)
        self.placeholder = ttk.Label(self.entry, text=placeholder, style="Muted.TLabel", cursor="xterm")
        self.placeholder.bind("<Button-1>", lambda _e: self.entry.focus_set())
        self.clear_button = ttk.Button(self, text="✕", width=2, command=self.clear, takefocus=False)
        self.entry.bind("<Escape>", lambda _e: self.clear())
        self.var.trace_add("write", lambda *_: self._toggle_clear())
        self._toggle_clear()

    @property
    def query(self):
        return fold(self.var.get().strip())

    def clear(self):
        self.var.set("")

    def focus(self):
        self.entry.focus_set()
        self.entry.select_range(0, "end")

    def _toggle_clear(self):
        if self.var.get():
            self.clear_button.pack(side="left", padx=(2, 0))
            self.placeholder.place_forget()
        else:
            self.clear_button.pack_forget()
            self.placeholder.place(x=6, rely=0.5, anchor="w")


class GameCombobox(ttk.Combobox):
    """Combobox of the games list whose drop-down narrows to what's typed.
    Free text is allowed (a new game); `value` is the cleaned text."""

    def __init__(self, master, games=(), **kwargs):
        super().__init__(master, **kwargs)
        self.set_games(games)
        self.bind("<KeyRelease>", self._filter)

    def set_games(self, games):
        self._games = list(games)
        self["values"] = self._games

    @property
    def value(self):
        return clean(self.get())

    def _filter(self, event):
        if event.keysym in ("Up", "Down", "Return", "KP_Enter", "Escape", "Tab"):
            return
        query = fold(self.get().strip())
        self["values"] = [g for g in self._games if query in fold(g)] if query else self._games
