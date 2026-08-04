from __future__ import annotations

import tkinter as tk
from tkinter import messagebox


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

    def attach_menu(self, menu: tk.Menu) -> None:
        self.menu = menu
        menu.add_command(
            label="Phone remote setup",
            command=self.show_phone_setup,
        )
        menu.add_checkbutton(
            label=self._screen_label(),
            variable=self.screen_variable,
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
        enabled = bool(self.screen_variable.get())
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
            messagebox.showinfo("Aksh Phone Remote", "Phone remote disabled hai.")
            return
        public_url = str(info["public_url"])
        if public_url:
            internet_text = f"Internet URL: {public_url}"
        elif info["tunnel_status"] in {"starting", "registering"}:
            internet_text = (
                "Internet URL: connect ho raha hai; 5-10 sec baad menu dobara kholein."
            )
        else:
            internet_text = "Internet URL: abhi available nahi hai."
        discovery_url = str(info.get("discovery_url", "")).strip()
        discovery_text = (
            f"Discovery relay: {discovery_url}"
            if discovery_url
            else "Discovery relay: not configured"
        )
        setup = (
            f"Device ID: {info['device_id']}\n"
            f"Local diagnostic URL: {info['local_url']}\n"
            f"{internet_text}\n"
            f"{discovery_text}\n"
            f"Pairing token: {info['token']}"
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(setup)
        messagebox.showinfo(
            "Aksh Phone Remote",
            "APK mein Device ID aur pairing token enter karein:\n\n"
            f"{setup}\n\n"
            "Apna Discovery relay URL APK mein bhi enter karein. Relay configured "
            "hone par tunnel URL automatic update hoga; Manual URL sirf fallback "
            "hai. Details laptop clipboard par copy hain.",
            parent=self.root,
        )

    def _screen_label(self) -> str:
        state = "On" if self.settings.remote_screen_enabled else "Off"
        return f"Remote screen access: {state}"
