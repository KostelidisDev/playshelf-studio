"""Date/time picker: an entry with a calendar button, stdlib only.

The value stays an ISO 8601 UTC string (YYYY-MM-DDTHH:MM:SSZ) in a
StringVar, so the entry can still be typed into or pasted; the popup just
fills it in. Tkinter has no date picker of its own, and the usual add-on
(tkcalendar) pulls in babel, which complicates the PyInstaller build.
"""

import calendar
import tkinter as tk
from datetime import datetime, timezone
from tkinter import font, ttk

from ..utils.dates import format_published_at, now_utc, parse_datetime

SELECTED_BG = "#2f6fdf"
SELECTED_FG = "#ffffff"


def parse_or_now(text):
    return parse_datetime(text) or now_utc()


class DateTimePicker(ttk.Frame):
    def __init__(self, master, value=""):
        super().__init__(master)
        self.var = tk.StringVar(value=value)
        self.entry = ttk.Entry(self, textvariable=self.var, width=24)
        self.entry.pack(side="left", fill="x", expand=True)
        ttk.Button(self, text="Pick…", command=self.open).pack(side="left", padx=(4, 0))
        self.entry.bind("<Alt-Down>", lambda _e: self.open())

    def open(self):
        popup = CalendarPopup(self, parse_or_now(self.var.get()))
        if popup.result is not None:
            self.var.set(format_published_at(popup.result))
        self.entry.focus_set()


class CalendarPopup(tk.Toplevel):
    """Modal month calendar plus hour/minute/second spinboxes (UTC)."""

    def __init__(self, picker, value):
        owner = picker.winfo_toplevel()
        super().__init__(owner)
        self.title("Pick date and time (UTC)")
        self.transient(owner)
        self.resizable(False, False)
        self.result = None
        self.selected = value.date()
        self.shown = value.replace(day=1).date()  # month on display
        self.bold = font.nametofont("TkDefaultFont").copy()
        self.bold.configure(weight="bold")

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        self._build_header(body)
        self.days = ttk.Frame(body)
        self.days.pack(pady=(6, 0))
        self._build_time(body, value)
        self._build_buttons(body)

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Prior>", lambda _e: self._move(-1))   # Page Up
        self.bind("<Next>", lambda _e: self._move(1))     # Page Down
        self._render()

        self.update_idletasks()
        x = picker.winfo_rootx()
        y = picker.winfo_rooty() + picker.winfo_height() + 4
        self.geometry(f"+{x}+{y}")
        grab_owner = owner.grab_current()
        self.grab_set()
        self.focus_set()
        self.wait_window(self)
        if grab_owner is not None and grab_owner.winfo_exists():
            grab_owner.grab_set()  # hand the modal grab back to the dialog

    # ---------- Layout ----------

    def _build_header(self, body):
        header = ttk.Frame(body)
        header.pack(fill="x")
        ttk.Button(header, text="«", width=3, command=lambda: self._move(-12)).pack(side="left")
        ttk.Button(header, text="‹", width=3, command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(header, text="»", width=3, command=lambda: self._move(12)).pack(side="right")
        ttk.Button(header, text="›", width=3, command=lambda: self._move(1)).pack(side="right")
        self.month_label = ttk.Label(header, anchor="center", font=self.bold)
        self.month_label.pack(side="left", fill="x", expand=True)

    def _build_time(self, body, value):
        row = ttk.Frame(body)
        row.pack(pady=(10, 0))
        ttk.Label(row, text="Time (UTC):").pack(side="left", padx=(0, 6))
        self.time_vars = []
        for i, (current, top) in enumerate([(value.hour, 23), (value.minute, 59), (value.second, 59)]):
            if i:
                ttk.Label(row, text=":").pack(side="left")
            var = tk.StringVar(value=f"{current:02d}")
            ttk.Spinbox(row, from_=0, to=top, wrap=True, width=3, format="%02.0f", textvariable=var).pack(side="left")
            self.time_vars.append((var, top))

    def _build_buttons(self, body):
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text="Now", command=self._now).pack(side="left")
        ttk.Button(row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(row, text="OK", command=self._ok).pack(side="right", padx=(0, 6))

    def _render(self):
        for child in self.days.winfo_children():
            child.destroy()
        self.month_label.configure(text=self.shown.strftime("%B %Y"))
        for col, name in enumerate(calendar.day_abbr):  # Monday first
            ttk.Label(self.days, text=name[:2], foreground="gray", anchor="center", width=4).grid(row=0, column=col)

        today = now_utc().date()
        weeks = calendar.Calendar().monthdatescalendar(self.shown.year, self.shown.month)
        for row, week in enumerate(weeks, start=1):
            for col, day in enumerate(week):
                if day.month != self.shown.month:
                    continue
                cell = tk.Label(self.days, text=str(day.day), width=4, pady=3, cursor="hand2",
                                font=self.bold if day == today else "TkDefaultFont")
                if day == self.selected:
                    cell.configure(bg=SELECTED_BG, fg=SELECTED_FG)
                cell.grid(row=row, column=col, padx=1, pady=1)
                cell.bind("<Button-1>", lambda _e, d=day: self._select(d))
                cell.bind("<Double-Button-1>", lambda _e, d=day: (self._select(d), self._ok()))

    # ---------- Actions ----------

    def _move(self, months):
        index = self.shown.year * 12 + self.shown.month - 1 + months
        self.shown = self.shown.replace(year=index // 12, month=index % 12 + 1)
        self._render()

    def _select(self, day):
        self.selected = day
        self._render()

    def _now(self):
        now = now_utc()
        self.selected = now.date()
        self.shown = self.selected.replace(day=1)
        for (var, _), value in zip(self.time_vars, (now.hour, now.minute, now.second)):
            var.set(f"{value:02d}")
        self._render()

    def _ok(self):
        parts = []
        for var, top in self.time_vars:
            try:
                parts.append(min(max(int(var.get()), 0), top))
            except ValueError:
                parts.append(0)
        self.result = datetime(self.selected.year, self.selected.month, self.selected.day, *parts, tzinfo=timezone.utc)
        self.destroy()
