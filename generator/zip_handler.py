"""ZIP file picker and extractor for Day One exports."""

import zipfile
import tkinter as tk
from tkinter import filedialog
from pathlib import Path


def pick_zip_path():
    """Show a file dialog and return the selected ZIP path, or None if cancelled."""
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Select Day One export ZIP",
        filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
    )
    root.destroy()
    return path if path else None


def unzip_to_folder(zip_path: str, dest_folder: str) -> Path:
    """Extract the ZIP to the given destination folder. Returns the destination path."""
    dest = Path(dest_folder)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    return dest
