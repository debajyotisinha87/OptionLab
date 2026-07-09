"""
Folder Picker

Opens a native OS folder-browse dialog. Only makes sense for a local,
single-user tool where the server process and the browser run on the
same machine (the assumption app/web/__main__.py's 127.0.0.1 binding
already makes).
"""

import threading

_lock = threading.Lock()


def pick_folder(initial_dir: str | None = None) -> str | None:
    """Opens a native folder-picker dialog synchronously and returns
    the chosen path, or None if the user cancelled. tkinter is
    imported here (not at module load) so a missing/broken tkinter
    install only breaks this one call, not the whole GUI's startup.
    Locked so two overlapping calls can't open two native dialogs at
    once."""

    with _lock:

        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:

            path = filedialog.askdirectory(initialdir=initial_dir or None)

        finally:

            root.destroy()

        return path or None
