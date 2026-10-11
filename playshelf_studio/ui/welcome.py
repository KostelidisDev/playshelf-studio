"""First-run screen, shown instead of the library until there's data."""

from tkinter import ttk

from ..config import APP_NAME


class WelcomeScreen(ttk.Frame):
    def __init__(self, master, on_import, on_empty, location):
        super().__init__(master, padding=24)
        box = ttk.Frame(self)
        box.place(relx=0.5, rely=0.42, anchor="center")
        ttk.Label(box, text=APP_NAME, style="Title.TLabel").pack()
        ttk.Label(
            box, style="Muted.TLabel", justify="center",
            text="Put together the PlayShelf catalog: hand-picked YouTube videos\n"
                 "from any creators, grouped by game. Then export the videos.csv\n"
                 "the site serves.",
        ).pack(pady=(6, 24))

        import_button = ttk.Button(box, text="Import PlayShelf's videos.csv…", default="active", command=on_import)
        import_button.pack(fill="x", ipady=4)
        ttk.Label(
            box, style="Muted.TLabel", justify="center",
            text="Its game titles become the games list.",
        ).pack(pady=(4, 16))
        ttk.Button(box, text="Start with an empty library", command=on_empty).pack(fill="x", ipady=4)

        ttk.Label(self, text=f"Data folder: {location}", style="Muted.TLabel").pack(side="bottom")
        self.import_button = import_button
