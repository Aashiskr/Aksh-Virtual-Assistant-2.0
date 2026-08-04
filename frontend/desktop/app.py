from __future__ import annotations

import logging
import queue
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from backend import AkshAssistant, load_settings
from backend.remote import RemoteCommandServer

from .first_run import ensure_first_run
from .capture_privacy import set_capture_excluded
from .hotkey import GlobalHotkey
from .meeting_ui import MeetingUI
from .panel import CommandPanel
from .pet_view import PetView
from .profile_ui import ProfileUI
from .remote_access_ui import RemoteAccessUI
from .theme import PANEL_BG, TEXT


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_ROOT = Path(__file__).resolve().parent
PET_SIZE_STEP = 16


def configure_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_dir / "aksh.log", encoding="utf-8")
    ]
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


class AkshPetApp:
    def __init__(self):
        self.settings, self.store = load_settings()
        configure_logging(self.settings.logs_dir)
        self.root = tk.Tk()
        self.root.withdraw()
        if not ensure_first_run(self.root, self.settings):
            self.root.destroy()
            raise SystemExit(0)
        self.events: queue.Queue[tuple[str, tuple]] = queue.Queue()
        self.view = PetView(
            self.root,
            self.settings,
            asset_path=DESKTOP_ROOT / "assets" / "aksh_pet.png",
            on_single_click=lambda: self.assistant.greet(),
            on_double_click=lambda: self._activate("pet"),
            on_context=self._show_context,
            on_moved=lambda x, y: self.store.update(pet_x=x, pet_y=y),
            on_close=self.close,
        )
        self.root.deiconify()
        self.root.after(50, lambda: set_capture_excluded(self.root))
        self.assistant = AkshAssistant(
            self.settings,
            status_callback=lambda *args: self.events.put(("status", args)),
            message_callback=lambda *args: self.events.put(("message", args)),
            meeting_callback=lambda *args: self.events.put(("meeting", args)),
        )
        self.remote = RemoteCommandServer(
            self.settings, self.assistant.run_remote_command
        )
        self.remote_ui = RemoteAccessUI(
            self.root,
            self.remote,
            self.settings,
            self.store,
        )
        self.panel = CommandPanel(
            self.root,
            on_talk=lambda: self._activate("panel"),
            on_send=self.assistant.process_typed,
            on_enroll=self._confirm_enrollment,
            allow_enrollment=self.settings.voice_lock_enabled,
        )
        self.meeting_ui = MeetingUI(self.root, self.assistant)
        self.profile_ui = ProfileUI(self.root, self.settings.data_dir)
        self._build_context()
        self.hotkey = GlobalHotkey(
            self.settings.hotkey,
            lambda: self.events.put(("activate", ("hotkey",))),
        )
        self.hotkey.start()
        self.root.after(50, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.assistant.start()
        self.remote.start()

    def _build_context(self) -> None:
        self.context = tk.Menu(
            self.root,
            tearoff=0,
            bg=PANEL_BG,
            fg=TEXT,
            activebackground="#293152",
            activeforeground=TEXT,
            bd=0,
        )
        self.context.add_command(
            label="Talk now", command=lambda: self._activate("menu")
        )
        self.context.add_command(label="Type a command", command=self.show_panel)
        self.meeting_ui.attach_menu(self.context)
        self.profile_ui.attach_menu(self.context)
        self.remote_ui.attach_menu(self.context)
        self.context.add_separator()
        if self.settings.voice_lock_enabled:
            self.context.add_command(
                label="Enroll owner voice", command=self._confirm_enrollment
            )
        else:
            self.context.add_command(label="Voice lock: Off", state="disabled")
        size_menu = tk.Menu(
            self.context,
            tearoff=0,
            bg=PANEL_BG,
            fg=TEXT,
            activebackground="#293152",
            activeforeground=TEXT,
        )
        size_menu.add_command(
            label="−  Decrease",
            command=lambda: self._adjust_pet_size(-PET_SIZE_STEP),
        )
        size_menu.add_command(
            label="+  Increase",
            command=lambda: self._adjust_pet_size(PET_SIZE_STEP),
        )
        self.context.add_cascade(label="Pet size", menu=size_menu)
        self.wake_variable = tk.BooleanVar(
            value=self.settings.wake_listener_enabled
        )
        self.context.add_checkbutton(
            label=self._microphone_menu_label(
                self.settings.wake_listener_enabled
            ),
            variable=self.wake_variable,
            command=self._toggle_wake,
        )
        self.microphone_menu_index = self.context.index("end")
        self.continuous_variable = tk.BooleanVar(
            value=self.settings.continuous_listening_enabled
        )
        self.context.add_checkbutton(
            label="Always listen (no wake word)",
            variable=self.continuous_variable,
            command=self._toggle_continuous,
        )
        self.context.add_separator()
        self.context.add_command(label="Exit Aksh", command=self.close)

    def _show_context(self, event) -> None:
        self.wake_variable.set(self.settings.wake_listener_enabled)
        self.continuous_variable.set(self.settings.continuous_listening_enabled)
        self._refresh_microphone_menu()
        self.meeting_ui.refresh_menu()
        self.remote_ui.refresh()
        try:
            self.context.tk_popup(event.x_root, event.y_root)
        finally:
            self.context.grab_release()

    def show_panel(self) -> None:
        self.panel.show(self.root.winfo_x(), self.root.winfo_y())

    def _confirm_enrollment(self) -> None:
        parent = self.panel.window or self.root
        if messagebox.askyesno(
            "Owner voice enrollment",
            "Quiet room mein 3 short voice samples record honge. Continue?",
            parent=parent,
        ):
            self.assistant.enroll_owner_voice()

    def _toggle_wake(self) -> None:
        enabled = bool(self.wake_variable.get())
        self.store.update(wake_listener_enabled=enabled)
        self.assistant.set_wake_listener_enabled(enabled)
        self._refresh_microphone_menu()

    @staticmethod
    def _microphone_menu_label(enabled: bool) -> str:
        return (
            "🎙  Microphone listening on"
            if enabled
            else "🔇  Microphone listening off"
        )

    def _refresh_microphone_menu(self) -> None:
        self.context.entryconfigure(
            self.microphone_menu_index,
            label=self._microphone_menu_label(
                bool(self.settings.wake_listener_enabled)
            ),
        )

    def _toggle_continuous(self) -> None:
        enabled = bool(self.continuous_variable.get())
        self.store.update(continuous_listening_enabled=enabled)
        self.assistant.set_continuous_listening_enabled(enabled)

    def _activate(self, source: str) -> None:
        if not self.settings.wake_listener_enabled:
            self.wake_variable.set(True)
            self.store.update(wake_listener_enabled=True)
        self.assistant.activate(source)

    def _set_pet_size(self, size: int) -> None:
        self.view.set_pet_size(size)
        actual_size = self.settings.pet_size
        self.store.update(
            pet_size=actual_size,
            pet_x=self.root.winfo_x(),
            pet_y=self.root.winfo_y(),
        )

    def _adjust_pet_size(self, delta: int) -> None:
        self._set_pet_size(self.settings.pet_size + int(delta))

    def _drain_events(self) -> None:
        try:
            while True:
                event, values = self.events.get_nowait()
                if event == "status":
                    state, text = values
                    if state == "sleeping" and self.wake_variable.get():
                        self.wake_variable.set(False)
                        self.store.update(wake_listener_enabled=False)
                        self._refresh_microphone_menu()
                    self.view.set_status(
                        state,
                        text,
                        self.assistant.friends_mode,
                        self.settings.voice_lock_enabled,
                    )
                elif event == "message":
                    self.view.show_message(*values)
                elif event == "activate":
                    self._activate(*values)
                elif event == "meeting":
                    self.meeting_ui.handle(*values)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(50, self._drain_events)

    def close(self) -> None:
        try:
            self.store.update(
                pet_x=self.root.winfo_x(), pet_y=self.root.winfo_y()
            )
        except Exception:
            pass
        self.hotkey.close()
        self.remote.close()
        self.assistant.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    AkshPetApp().run()
