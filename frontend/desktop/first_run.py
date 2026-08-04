from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

from backend.config import AkshSettings
from backend.credentials import GroqKeyStore


def ensure_first_run(root: tk.Tk, settings: AkshSettings) -> bool:
    return ensure_groq_key(root, settings) and ensure_owner_name(root, settings)


def ensure_groq_key(root: tk.Tk, settings: AkshSettings) -> bool:
    """Collect a private Groq key without bundling it in a release."""
    if _looks_like_groq_key(settings.groq_api_key):
        return True

    messagebox.showinfo(
        "Aksh first-time setup",
        "Har laptop apni Groq API key use karta hai. Key sirf is laptop ki "
        ".env file mein save hogi; phone APK mein kabhi nahi jayegi.",
        parent=root,
    )
    while True:
        key = simpledialog.askstring(
            "Connect Groq",
            "Apni Groq API key paste karein:",
            show="*",
            parent=root,
        )
        if key is None:
            return False
        key = key.strip()
        if _looks_like_groq_key(key):
            GroqKeyStore(settings.data_dir).save(key)
            settings.groq_api_key = key
            return True
        messagebox.showerror(
            "Invalid Groq key",
            "Valid Groq key gsk_ se start hoti hai. Dobara paste karein.",
            parent=root,
        )


def ensure_owner_name(root: tk.Tk, settings: AkshSettings) -> bool:
    if settings.owner_name.strip().casefold() not in {"", "owner", "user"}:
        return True
    while True:
        name = simpledialog.askstring(
            "Personalize Aksh",
            "Aksh aapko kis naam se bulaye?",
            parent=root,
        )
        if name is None:
            return False
        name = " ".join(name.split())
        if 2 <= len(name) <= 40:
            _save_environment_value(
                settings.project_root / ".env", "AKSH_OWNER_NAME", name
            )
            settings.owner_name = name
            return True
        messagebox.showerror(
            "Invalid name",
            "2 se 40 characters ka naam enter karein.",
            parent=root,
        )


def _looks_like_groq_key(value: str) -> bool:
    return value.startswith("gsk_") and len(value) >= 24


def _save_environment_value(path: Path, name: str, value: str) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    kept = [line for line in lines if not line.startswith(f"{name}=")]
    path.write_text(
        "\n".join([f"{name}={value}", *kept]).rstrip() + "\n",
        encoding="utf-8",
    )
