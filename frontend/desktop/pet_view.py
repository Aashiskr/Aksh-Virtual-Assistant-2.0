from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from pathlib import Path
from typing import Callable

from .pet_animation import PetAnimator
from .pet_geometry import clamp_pet_position, geometry_offset
from .theme import BORDER, MUTED, PANEL_BG, STATE_COLORS, TEXT, TRANSPARENT


PASSIVE_STATUS_STATES = {"idle", "sleeping"}
MESSAGE_STATUS_MILLISECONDS = 4500


def _screen_geometry(root: tk.Tk) -> tuple[int, int, int, int]:
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            left = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            top = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            if width > 0 and height > 0:
                return left, top, width, height
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class PetView:
    def __init__(
        self,
        root: tk.Tk,
        settings,
        *,
        asset_path: Path,
        on_single_click: Callable[[], None],
        on_double_click: Callable[[], None],
        on_context: Callable[[tk.Event], None],
        on_moved: Callable[[int, int], None],
        on_close: Callable[[], None],
    ):
        self.root = root
        self.settings = settings
        self.on_single_click = on_single_click
        self.on_double_click = on_double_click
        self.on_context = on_context
        self.on_moved = on_moved
        self.on_close = on_close
        self.asset_path = asset_path
        self.animator = PetAnimator(asset_path, settings.pet_size)
        self.width = max(170, settings.pet_size + 48)
        self.height = settings.pet_size + 92
        self._state = "idle"
        self._status = "Starting…"
        self._friends_mode = False
        self._voice_lock_enabled = settings.voice_lock_enabled
        self._drag_origin = None
        self._dragged = False
        self._single_job = None
        self._double_seen = False
        self._status_hide_job = None
        self._configure_window()
        self._build()
        self.root.after(350, self._animate)

    def _configure_window(self) -> None:
        self.root.title("Aksh AI")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        screen_left, screen_top, screen_w, screen_h = _screen_geometry(self.root)
        x = self.settings.pet_x
        y = self.settings.pet_y
        x = screen_left + screen_w - self.width - 32 if x is None else x
        y = screen_top + screen_h - self.height - 70 if y is None else y
        x, y = clamp_pet_position(
            x,
            y,
            screen_width=screen_w,
            screen_height=screen_h,
            screen_left=screen_left,
            screen_top=screen_top,
            window_width=self.width,
            window_height=self.height,
            pet_size=self.settings.pet_size,
        )
        self.root.geometry(
            f"{self.width}x{self.height}{geometry_offset(x, y)}"
        )

    def _build(self) -> None:
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANSPARENT,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        center_x = self.width // 2
        radius = self.settings.pet_size // 2 + 5
        center_y = radius + 5
        self.pet_center_x = center_x
        self.pet_center_y = center_y
        self.pet_image, _ = self.animator.next_frame(self._state)
        self.pet_item = self.canvas.create_image(
            center_x, center_y, image=self.pet_image
        )
        self.status_panel = self.canvas.create_rectangle(
            10,
            self.height - 68,
            self.width - 10,
            self.height - 10,
            fill=PANEL_BG,
            outline=BORDER,
        )
        self.name_text = self.canvas.create_text(
            22,
            self.height - 53,
            text="AKSH",
            fill=STATE_COLORS["idle"],
            anchor="w",
            font=("Segoe UI Semibold", 10),
        )
        self.mode_text = self.canvas.create_text(
            self.width - 20,
            self.height - 53,
            text="OWNER",
            fill=MUTED,
            anchor="e",
            font=("Segoe UI Semibold", 8),
        )
        self.status_text = self.canvas.create_text(
            self.width // 2,
            self.height - 29,
            text="Starting…",
            fill=TEXT,
            width=self.width - 38,
            justify="center",
            font=("Segoe UI", 9),
        )
        self._set_status_visible(False)
        for item in (self.pet_item,):
            self.canvas.tag_bind(item, "<ButtonPress-1>", self._drag_start)
            self.canvas.tag_bind(item, "<Double-Button-1>", self._double_click)
            self.canvas.tag_bind(item, "<Button-3>", self.on_context)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Button-3>", self.on_context)

    def set_status(
        self,
        state: str,
        text: str,
        friends_mode: bool,
        voice_lock_enabled: bool = True,
    ) -> None:
        self._state = state
        self._status = text
        self._friends_mode = friends_mode
        self._voice_lock_enabled = voice_lock_enabled
        self.animator.set_state(state)
        color = STATE_COLORS.get(state, STATE_COLORS["idle"])
        self.canvas.itemconfigure(self.name_text, fill=color)
        self.canvas.itemconfigure(self.status_text, text=text[:90])
        mode = "OPEN" if not voice_lock_enabled else (
            "FRIENDS" if friends_mode else "OWNER"
        )
        self.canvas.itemconfigure(
            self.mode_text, text=mode, fill=color if friends_mode else MUTED
        )
        if state in PASSIVE_STATUS_STATES:
            if self._status_hide_job is None:
                self._set_status_visible(False)
        else:
            self._cancel_status_hide()
            self._set_status_visible(True)

    def set_pet_size(self, size: int) -> None:
        size = max(96, min(320, int(size)))
        if size == self.settings.pet_size:
            return
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.settings.pet_size = size
        self.animator.set_size(size)
        self.width = max(170, size + 48)
        self.height = size + 92
        screen_left, screen_top, screen_w, screen_h = _screen_geometry(self.root)
        x, y = clamp_pet_position(
            x,
            y,
            screen_width=screen_w,
            screen_height=screen_h,
            screen_left=screen_left,
            screen_top=screen_top,
            window_width=self.width,
            window_height=self.height,
            pet_size=size,
        )
        self.canvas.destroy()
        self.root.geometry(
            f"{self.width}x{self.height}{geometry_offset(x, y)}"
        )
        self._build()
        self.set_status(
            self._state,
            self._status,
            self._friends_mode,
            self._voice_lock_enabled,
        )
        self.on_moved(x, y)

    def show_message(self, role: str, text: str) -> None:
        self._cancel_status_hide()
        self._set_status_visible(True)
        prefix = "You: " if role == "you" else ""
        self.canvas.itemconfigure(self.status_text, text=(prefix + text)[:78])
        if role == "you":
            self.animator.react("listening", 8)
        elif role == "permission":
            self.animator.react("thinking", 14)
        else:
            self.animator.react("happy", 12)
        self._status_hide_job = self.root.after(
            MESSAGE_STATUS_MILLISECONDS,
            self._hide_transient_status,
        )

    def _set_status_visible(self, visible: bool) -> None:
        state = "normal" if visible else "hidden"
        for item in (
            self.status_panel,
            self.name_text,
            self.mode_text,
            self.status_text,
        ):
            self.canvas.itemconfigure(item, state=state)

    def _cancel_status_hide(self) -> None:
        if self._status_hide_job is not None:
            self.root.after_cancel(self._status_hide_job)
            self._status_hide_job = None

    def _hide_transient_status(self) -> None:
        self._status_hide_job = None
        if self._state in PASSIVE_STATUS_STATES:
            self._set_status_visible(False)

    def _drag_start(self, event) -> None:
        self._dragged = False
        self._drag_origin = (
            event.x_root,
            event.y_root,
            self.root.winfo_x(),
            self.root.winfo_y(),
        )

    def _drag_move(self, event) -> None:
        if not self._drag_origin:
            return
        start_x, start_y, window_x, window_y = self._drag_origin
        dx, dy = event.x_root - start_x, event.y_root - start_y
        self._dragged = self._dragged or abs(dx) + abs(dy) > 5
        screen_left, screen_top, screen_w, screen_h = _screen_geometry(self.root)
        x, y = clamp_pet_position(
            window_x + dx,
            window_y + dy,
            screen_width=screen_w,
            screen_height=screen_h,
            screen_left=screen_left,
            screen_top=screen_top,
            window_width=self.width,
            window_height=self.height,
            pet_size=self.settings.pet_size,
        )
        self.root.geometry(geometry_offset(x, y))

    def _drag_end(self, event) -> None:
        self._drag_origin = None
        if self._double_seen:
            self._double_seen = False
            return
        if self._dragged:
            self.on_moved(self.root.winfo_x(), self.root.winfo_y())
            return
        if self._single_job:
            self.root.after_cancel(self._single_job)
        self._single_job = self.root.after(260, self.on_single_click)

    def _double_click(self, event) -> None:
        self._double_seen = True
        if self._single_job:
            self.root.after_cancel(self._single_job)
            self._single_job = None
        self.on_double_click()

    def _animate(self) -> None:
        self.pet_image, offset_y = self.animator.next_frame(self._state)
        self.canvas.itemconfigure(self.pet_item, image=self.pet_image)
        self.canvas.coords(
            self.pet_item,
            self.pet_center_x,
            self.pet_center_y + offset_y,
        )
        if self.root.winfo_exists():
            self.root.after(120, self._animate)
