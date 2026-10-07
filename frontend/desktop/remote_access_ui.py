from __future__ import annotations

import subprocess
import tkinter as tk
from tkinter import messagebox

from .theme import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    MUTED,
    PANEL_BG,
    SURFACE,
    SURFACE_ALT,
    TEXT,
)


PHONE_SETUP_FIELDS = (
    ("discovery_url", "Cloudflare discovery relay URL"),
    ("device_id", "Device ID"),
    ("token", "Pairing token"),
    ("manual_url", "Manual laptop URL"),
)


def phone_setup_values(info: dict[str, object]) -> dict[str, str]:
    """Return only the four values the Android setup screen needs."""
    return {
        "discovery_url": str(info.get("discovery_url", "")).strip(),
        "device_id": str(info.get("device_id", "")).strip(),
        "token": str(info.get("token", "")).strip(),
        "manual_url": str(info.get("public_url", "")).strip(),
    }


class RemoteAccessUI:
    def __init__(self, root, remote, settings, store):
        self.root = root
        self.remote = remote
        self.settings = settings
        self.store = store
        self.screen_variable = tk.BooleanVar(
            value=settings.remote_screen_enabled
        )
        self.menu: tk.Menu | None = None
        self.screen_menu_index: int | None = None
        self.setup_window: tk.Toplevel | None = None
        self.setup_variables: dict[str, tk.StringVar] = {}
        self.setup_copy_buttons: dict[str, tk.Button] = {}
        self.setup_copy_values: dict[str, str] = {}
        self.setup_status: tk.Label | None = None

    def attach_menu(self, menu: tk.Menu) -> None:
        self.menu = menu
        menu.add_command(
            label="Phone remote setup",
            command=self.show_phone_setup,
        )
        menu.add_command(
            label="Install phone fingerprint unlock",
            command=self.open_secure_login_setup,
        )
        menu.add_command(
            label=self._screen_label(),
            command=self.toggle_remote_screen,
        )
        self.screen_menu_index = menu.index("end")

    def refresh(self) -> None:
        self.screen_variable.set(self.settings.remote_screen_enabled)
        if self.menu is not None and self.screen_menu_index is not None:
            self.menu.entryconfigure(
                self.screen_menu_index,
                label=self._screen_label(),
            )

    def toggle_remote_screen(self) -> None:
        enabled = not bool(self.settings.remote_screen_enabled)
        self.screen_variable.set(enabled)
        if enabled and not messagebox.askyesno(
            "Enable Aksh Remote Screen",
            (
                "Paired phone laptop ki current screen dekh aur mouse/keyboard "
                "control kar sakega. Sirf apne trusted phone par enable karein.\n\n"
                "Remote screen access enable karna hai?"
            ),
            parent=self.root,
        ):
            self.screen_variable.set(False)
            self.refresh()
            return
        self.store.update(remote_screen_enabled=enabled)
        self.remote.set_screen_enabled(enabled)
        self.refresh()
        message = (
            "Remote screen enabled. Phone APK se View & Control khol sakte hain."
            if enabled
            else "Remote screen disabled. Active phone sessions disconnect ho gaye."
        )
        messagebox.showinfo("Aksh Remote Screen", message, parent=self.root)

    def show_phone_setup(self) -> None:
        info = self.remote.connection_info()
        if not info["enabled"]:
            messagebox.showinfo(
                "Aksh Phone Remote",
                "Phone remote disabled hai.",
                parent=self.root,
            )
            return
        if self.setup_window is not None and self.setup_window.winfo_exists():
            self._refresh_phone_setup(info)
            self.setup_window.deiconify()
            self.setup_window.lift()
            self.setup_window.focus_force()
            return
        self._build_phone_setup_window()
        self._refresh_phone_setup(info)

    def _build_phone_setup_window(self) -> None:
        window = tk.Toplevel(self.root)
        self.setup_window = window
        window.title("Aksh Phone Remote Setup")
        window.configure(bg=PANEL_BG)
        window.geometry("820x430")
        window.minsize(700, 390)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self._close_phone_setup)

        tk.Label(
            window,
            text="Connect your phone to Aksh",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 18),
            anchor="w",
        ).pack(fill="x", padx=24, pady=(22, 4))
        tk.Label(
            window,
            text=(
                "Android app mein ye four values enter karein. Kisi ek value ko "
                "copy karne ke liye uske saamne Copy click karein."
            ),
            bg=PANEL_BG,
            fg=MUTED,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=24, pady=(0, 18))

        form = tk.Frame(window, bg=PANEL_BG)
        form.pack(fill="both", expand=True, padx=24)
        form.grid_columnconfigure(1, weight=1)

        self.setup_variables = {}
        self.setup_copy_buttons = {}
        for row, (key, label) in enumerate(PHONE_SETUP_FIELDS):
            tk.Label(
                form,
                text=label,
                bg=PANEL_BG,
                fg=TEXT,
                font=("Segoe UI Semibold", 10),
                anchor="w",
            ).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=8)
            variable = tk.StringVar(window)
            self.setup_variables[key] = variable
            tk.Entry(
                form,
                textvariable=variable,
                state="readonly",
                readonlybackground=SURFACE,
                fg=TEXT,
                relief="solid",
                bd=1,
                highlightbackground=BORDER,
                font=("Consolas", 10),
            ).grid(row=row, column=1, sticky="ew", pady=8, ipady=7)
            button = tk.Button(
                form,
                text="Copy",
                command=lambda selected=key: self._copy_phone_setup_value(
                    selected
                ),
                bg=SURFACE_ALT,
                fg=TEXT,
                activebackground="#dfe3de",
                activeforeground=TEXT,
                disabledforeground=MUTED,
                relief="flat",
                cursor="hand2",
                width=9,
            )
            button.grid(row=row, column=2, padx=(12, 0), pady=8, ipady=4)
            self.setup_copy_buttons[key] = button

        footer = tk.Frame(window, bg=PANEL_BG)
        footer.pack(fill="x", padx=24, pady=(14, 22))
        self.setup_status = tk.Label(
            footer,
            text="",
            bg=PANEL_BG,
            fg=ACCENT,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.setup_status.pack(side="left", fill="x", expand=True)
        self._setup_button(footer, "Close", self._close_phone_setup).pack(
            side="right", padx=(8, 0)
        )
        self._setup_button(footer, "Refresh URL", self._refresh_phone_setup).pack(
            side="right", padx=(8, 0)
        )
        self._setup_button(
            footer,
            "Copy all",
            self._copy_all_phone_setup,
            accent=True,
        ).pack(side="right")

        window.lift()
        window.focus_force()

    def _refresh_phone_setup(
        self,
        info: dict[str, object] | None = None,
    ) -> None:
        if self.setup_window is None or not self.setup_window.winfo_exists():
            return
        details = info or self.remote.connection_info()
        values = phone_setup_values(details)
        self.setup_copy_values = values
        tunnel_status = str(details.get("tunnel_status", "")).strip()

        for key, _ in PHONE_SETUP_FIELDS:
            value = values[key]
            if value:
                display = value
            elif key == "discovery_url":
                display = "Not configured"
            elif key == "manual_url" and tunnel_status in {
                "starting",
                "registering",
            }:
                display = "Connecting... click Refresh URL in a few seconds"
            else:
                display = "Not available"
            self.setup_variables[key].set(display)
            self.setup_copy_buttons[key].configure(
                state="normal" if value else "disabled"
            )

        if values["manual_url"]:
            status = "Manual laptop URL is ready. Pairing token private rakhein."
        elif tunnel_status in {"starting", "registering"}:
            status = "Cloudflare tunnel connect ho raha hai..."
        else:
            status = "Manual URL unavailable. Internet/cloudflared check karein."
        self._set_setup_status(status, clear_after=False)

    def _copy_phone_setup_value(self, key: str) -> None:
        value = self.setup_copy_values.get(key, "")
        if not value:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()
        label = dict(PHONE_SETUP_FIELDS).get(key, "Value")
        self._set_setup_status(f"{label} copied.")

    def _copy_all_phone_setup(self) -> None:
        lines = []
        for key, label in PHONE_SETUP_FIELDS:
            value = self.setup_copy_values.get(key, "") or "Not available"
            lines.append(f"{label}: {value}")
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.root.update_idletasks()
        self._set_setup_status("All four values copied.")

    def _set_setup_status(self, text: str, *, clear_after: bool = True) -> None:
        if self.setup_status is None or not self.setup_status.winfo_exists():
            return
        self.setup_status.configure(text=text)
        if clear_after:
            self.root.after(2400, self._clear_setup_status)

    def _clear_setup_status(self) -> None:
        if self.setup_status is not None and self.setup_status.winfo_exists():
            self.setup_status.configure(text="")

    def _close_phone_setup(self) -> None:
        if self.setup_window is not None and self.setup_window.winfo_exists():
            self.setup_window.destroy()
        self.setup_window = None
        self.setup_variables = {}
        self.setup_copy_buttons = {}
        self.setup_copy_values = {}
        self.setup_status = None

    @staticmethod
    def _setup_button(
        parent: tk.Misc,
        text: str,
        command,
        *,
        accent: bool = False,
    ) -> tk.Button:
        background = ACCENT if accent else SURFACE_ALT
        active = ACCENT_HOVER if accent else "#dfe3de"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg="#ffffff" if accent else TEXT,
            activebackground=active,
            activeforeground="#ffffff" if accent else TEXT,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
        )

    def open_secure_login_setup(self) -> None:
        if not messagebox.askyesno(
            "Install phone fingerprint unlock",
            (
                "Windows will request administrator approval and then ask for "
                "this account's PASSWORD once (not the Hello PIN). Aksh stores "
                "it as machine-bound encrypted data and releases it only after "
                "a signed phone fingerprint approval.\n\n"
                "Windows PIN/password sign-in will remain available. Continue?"
            ),
            parent=self.root,
        ):
            return
        installer = (
            self.settings.project_root
            / "infrastructure"
            / "windows"
            / "install_phone_unlock.ps1"
        )
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(installer),
                ],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except OSError as exception:
            messagebox.showerror(
                "Aksh Phone Unlock",
                f"Installer could not start: {exception}",
                parent=self.root,
            )

    def _screen_label(self) -> str:
        state = "On" if self.settings.remote_screen_enabled else "Off"
        return f"Remote screen access: {state}"
