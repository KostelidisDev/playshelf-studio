"""The small modal dialog for adding or renaming a game. Videos are edited
in the main window's details pane instead."""

import tkinter as tk
from tkinter import ttk

from ..core import ConflictError, PlayShelfError


class GameDialog(tk.Toplevel):
    """Asks for a game title; `result` is the saved title, or None if cancelled.
    Errors are shown inside the dialog, which stays open to fix them."""

    def __init__(self, app, original=None):
        super().__init__(app)
        self.app = app
        self.original = original
        self.result = None
        self.title("Rename game" if original else "New game")
        self.transient(app)
        self.resizable(False, False)

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Title").pack(anchor="w", pady=(0, 2))
        self.var = tk.StringVar(value=original or "")
        self.entry = ttk.Entry(body, textvariable=self.var, width=44)
        self.entry.pack(fill="x")
        if original:
            count = app.library.video_count(original)
            if count:
                note = f"Its {count} video{'s' if count != 1 else ''} will use the new title."
                ttk.Label(body, text=note, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        self.error = ttk.Label(body, style="Error.TLabel", wraplength=320, justify="left")
        self.error.pack(anchor="w", pady=(6, 0))
        self.var.trace_add("write", lambda *_: self.error.configure(text=""))

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Rename" if original else "Add", default="active",
                   command=self._ok).pack(side="right", padx=(0, 6))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<KP_Enter>", lambda _e: self._ok())

        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.entry.focus_set()
        self.entry.select_range(0, "end")
        self.wait_window(self)

    def _ok(self):
        library = self.app.library
        try:
            if self.original:
                self.result = library.rename_game(self.original, self.var.get())
            else:
                self.result = library.add_game(self.var.get())
        except ConflictError:
            self.destroy()
            self.app.handle_conflict()
            return
        except PlayShelfError as e:
            self.error.configure(text=str(e))
            self.bell()
            return
        self.destroy()
