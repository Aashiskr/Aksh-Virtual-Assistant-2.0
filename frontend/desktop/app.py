from __future__ import annotations

import logging
import queue
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from backend import AkshAssistant, load_settings
from backend.remote import RemoteCommandServer

from .capture_privacy import (
    exclude_popup_menus_from_capture,
    set_capture_excluded,
)
from .context_menu import build_context_menu
from .first_run import ensure_first_run
from .hotkey import GlobalHotkey
from .meeting_ui import MeetingUI
from .notebook_ui import TaskNotebookUI
from .panel import CommandPanel
from .pet_view import PetView
from .profile_ui import ProfileUI
from .remote_access_ui import RemoteAccessUI
from .settings_ui import SettingsPanel
from .window_behavior import hide_from_taskbar


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
        self.root.attributes("-alpha", 0.0)
        hide_from_taskbar(self.root)
        set_capture_excluded(self.root)
        self.root.deiconify()
        self.root.after_idle(
            lambda: self.root.attributes("-alpha", 1.0)
        )
        self.root.after(50, lambda: hide_from_taskbar(self.root))
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
        self.notebook_ui = TaskNotebookUI(
            self.root,
            self.assistant.brain.notebook,
        )
        self.profile_ui = ProfileUI(self.root, self.settings.data_dir)
        self.settings_ui = SettingsPanel(
            self.root,
            self.settings,
            on_wake=self._set_wake_enabled,
            on_double_clap=self._set_double_clap_enabled,
            on_continuous=self._set_continuous_enabled,
            on_enroll=self._confirm_enrollment,
        )
        self._build_context()
        exclude_popup_menus_from_capture()
        self.root.after_idle(exclude_popup_menus_from_capture)
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
        (
            self.context,
            self.microphone_menu_index,
            self.wake_variable,
            self.double_clap_variable,
            self.continuous_variable,
        ) = build_context_menu(self, PET_SIZE_STEP)

    def _show_context(self, event) -> None:
        self.wake_variable.set(self.settings.wake_listener_enabled)
        self.double_clap_variable.set(self.settings.double_clap_enabled)
        self.continuous_variable.set(self.settings.continuous_listening_enabled)
        self._refresh_microphone_menu()
        self.settings_ui.refresh()
        self.meeting_ui.refresh_menu()
        self.remote_ui.refresh()
        exclude_popup_menus_from_capture()
        try:
            self.context.tk_popup(event.x_root, event.y_root)
        finally:
            self.context.grab_release()

    def show_panel(self) -> None:
        self.panel.show(self.root.winfo_x(), self.root.winfo_y())

    def show_settings(self) -> None:
        self.settings_ui.show(self.root.winfo_x(), self.root.winfo_y())

    def _open_notebook_pdf(self) -> None:
        self.assistant.brain.notebook.refresh_workspace()
        result = self.assistant.notebook_exporter.export_and_open()
        self.view.show_message("aksh", result.message)

    def _confirm_enrollment(self) -> None:
        parent = self.panel.window or self.root
        if messagebox.askyesno(
            "Owner voice enrollment",
            "Quiet room mein 3 short voice samples record honge. Continue?",
            parent=parent,
        ):
            self.assistant.enroll_owner_voice()

    def _toggle_wake(self) -> None:
        self._set_wake_enabled(bool(self.wake_variable.get()))

    def _set_wake_enabled(self, enabled: bool) -> None:
        self.wake_variable.set(bool(enabled))
        values = {"wake_listener_enabled": enabled}
        if not enabled:
            self.double_clap_variable.set(False)
            values["double_clap_enabled"] = False
        self.store.update(**values)
        self.assistant.set_wake_listener_enabled(enabled)
        self._refresh_microphone_menu()

    @staticmethod
    def _microphone_menu_label(enabled: bool) -> str:
        return "🎙  Microphone listening on" if enabled else "🔇  Microphone listening off"

    def _refresh_microphone_menu(self) -> None:
        self.context.entryconfigure(
            self.microphone_menu_index,
            label=self._microphone_menu_label(
                bool(self.settings.wake_listener_enabled)
            ),
        )

    def _toggle_continuous(self) -> None:
        self._set_continuous_enabled(bool(self.continuous_variable.get()))

    def _set_continuous_enabled(self, enabled: bool) -> None:
        self.continuous_variable.set(bool(enabled))
        self.store.update(continuous_listening_enabled=enabled)
        self.assistant.set_continuous_listening_enabled(enabled)

    def _toggle_double_clap(self) -> None:
        self._set_double_clap_enabled(bool(self.double_clap_variable.get()))

    def _set_double_clap_enabled(self, enabled: bool) -> None:
        self.double_clap_variable.set(bool(enabled))
        self.store.update(double_clap_enabled=enabled)
        self.assistant.set_double_clap_enabled(enabled)

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
                    wake_enabled = bool(self.settings.wake_listener_enabled)
                    settings_changed = False
                    if bool(self.wake_variable.get()) != wake_enabled:
                        self.wake_variable.set(wake_enabled)
                        self.store.update(wake_listener_enabled=wake_enabled)
                        self._refresh_microphone_menu()
                        settings_changed = True
                    double_clap_enabled = bool(
                        self.settings.double_clap_enabled
                    )
                    if (
                        bool(self.double_clap_variable.get())
                        != double_clap_enabled
                    ):
                        self.double_clap_variable.set(double_clap_enabled)
                        self.store.update(
                            double_clap_enabled=double_clap_enabled
                        )
                        settings_changed = True
                    if settings_changed:
                        self.settings_ui.refresh()
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
