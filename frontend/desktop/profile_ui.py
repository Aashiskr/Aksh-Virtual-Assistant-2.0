from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from backend.profile import UserProfileStore

from .theme import PANEL_BG, SURFACE_ALT, TEXT


class ProfileUI:
    def __init__(self, root: tk.Tk, data_dir: Path):
        self.root = root
        self.store = UserProfileStore(data_dir)

    def attach_menu(self, parent: tk.Menu) -> None:
        menu = tk.Menu(
            parent,
            tearoff=0,
            bg=PANEL_BG,
            fg=TEXT,
            activebackground=SURFACE_ALT,
            activeforeground=TEXT,
        )
        menu.add_command(label="Import / Replace CV…", command=self.import_cv)
        menu.add_command(label="Profile status", command=self.show_status)
        menu.add_command(label="Remove profile", command=self.remove_profile)
        parent.add_cascade(label="My CV / Profile", menu=menu)

    def import_cv(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Choose CV or profile document",
            filetypes=[
                ("CV documents", "*.pdf *.docx *.txt *.md *.rst"),
                ("CV images", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("All supported files", "*.*"),
            ],
        )
        if not selected:
            return
        try:
            value = self.store.import_file(Path(selected))
        except Exception as exc:
            messagebox.showerror("Aksh Profile", str(exc), parent=self.root)
            return
        messagebox.showinfo(
            "Aksh Profile",
            (
                f"{value['source_name']} imported successfully.\n"
                f"{value['characters']} characters stored locally.\n\n"
                "Aksh relevant answers ke liye is context ko Groq ke saath "
                "use karega."
            ),
            parent=self.root,
        )

    def show_status(self) -> None:
        value = self.store.load()
        if not value:
            messagebox.showinfo(
                "Aksh Profile",
                "Abhi koi CV/profile imported nahi hai.",
                parent=self.root,
            )
            return
        messagebox.showinfo(
            "Aksh Profile",
            (
                f"File: {value.get('source_name', 'Unknown')}\n"
                f"Imported: {value.get('imported_at', 'Unknown')}\n"
                f"Extracted characters: {value.get('characters', 0)}"
            ),
            parent=self.root,
        )

    def remove_profile(self) -> None:
        if not self.store.load():
            self.show_status()
            return
        if not messagebox.askyesno(
            "Remove Aksh Profile",
            "Stored CV/profile text remove karna hai?",
            parent=self.root,
        ):
            return
        self.store.remove()
        messagebox.showinfo(
            "Aksh Profile",
            "Stored CV/profile removed.",
            parent=self.root,
        )
