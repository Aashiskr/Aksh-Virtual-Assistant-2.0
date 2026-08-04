from __future__ import annotations

import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from ..models import ActionResult
from .base import ActionGroup


class DesktopActions(ActionGroup):
    def open_app(self, parameters: dict[str, Any]) -> ActionResult:
        target = self.required(parameters, "target")
        safe_target = re.sub(r"[^\w .+()-]", "", target).strip()
        if not safe_target:
            raise ValueError("Invalid app name")
        try:
            subprocess.Popen([safe_target])
        except (FileNotFoundError, OSError):
            import pyautogui

            pyautogui.press("win")
            time.sleep(0.3)
            pyautogui.write(safe_target, interval=0.03)
            pyautogui.press("enter")
        return ActionResult(True, f"{safe_target} open kar raha hoon.")

    def browser_control(self, parameters: dict[str, Any]) -> ActionResult:
        import pyautogui

        option = self.required(parameters, "option")
        hotkeys: dict[str, tuple[str, ...]] = {
            "new_tab": ("ctrl", "t"),
            "close_tab": ("ctrl", "w"),
            "private_window": ("ctrl", "shift", "n"),
            "zoom_in": ("ctrl", "+"),
            "zoom_out": ("ctrl", "-"),
            "forward": ("alt", "right"),
            "back": ("alt", "left"),
            "fullscreen": ("f11",),
            "history": ("ctrl", "h"),
            "next_tab": ("ctrl", "tab"),
            "previous_tab": ("ctrl", "shift", "tab"),
            "refresh": ("ctrl", "r"),
        }
        if option == "scroll_up":
            pyautogui.scroll(600)
        elif option == "scroll_down":
            pyautogui.scroll(-600)
        elif option == "click":
            pyautogui.click()
        elif option in hotkeys:
            keys = hotkeys[option]
            pyautogui.press(keys[0]) if len(keys) == 1 else pyautogui.hotkey(*keys)
        else:
            return ActionResult(False, f"Unknown browser option: {option}")
        return ActionResult(True, f"Browser {option.replace('_', ' ')} done.")

    def youtube_control(self, parameters: dict[str, Any]) -> ActionResult:
        import pyautogui

        option = self.required(parameters, "option")
        keys: dict[str, tuple[str, ...]] = {
            "play_pause": ("k",),
            "mute": ("m",),
            "volume_up": ("up",),
            "volume_down": ("down",),
            "forward": ("l",),
            "backward": ("j",),
            "fullscreen": ("f",),
            "miniplayer": ("i",),
            "theater": ("t",),
            "next": ("shift", "n"),
            "previous": ("shift", "p"),
            "captions": ("c",),
            "home": ("0",),
        }
        if option not in keys:
            return ActionResult(False, f"Unknown YouTube option: {option}")
        command = keys[option]
        pyautogui.press(command[0]) if len(command) == 1 else pyautogui.hotkey(*command)
        return ActionResult(True, f"YouTube {option.replace('_', ' ')} done.")

    def window_control(self, parameters: dict[str, Any]) -> ActionResult:
        import pyautogui

        option = self.required(parameters, "option")
        shortcuts = {
            "close": ("alt", "f4"),
            "minimize": ("win", "down"),
            "maximize": ("win", "up"),
            "show_desktop": ("win", "d"),
        }
        if option not in shortcuts:
            return ActionResult(False, f"Unknown window option: {option}")
        pyautogui.hotkey(*shortcuts[option])
        return ActionResult(True, f"Window {option.replace('_', ' ')} done.")

    def switch_window(self, parameters: dict[str, Any]) -> ActionResult:
        target = self.required(parameters, "target")
        from ..capabilities.windows import switch_to_app

        found = switch_to_app(target)
        message = (
            f"{target} par switch kar diya."
            if found
            else f"{target} ki open window nahi mili."
        )
        return ActionResult(found, message)

    def battery_status(self, parameters: dict[str, Any]) -> ActionResult:
        battery = psutil.sensors_battery()
        if battery is None:
            return ActionResult(False, "Battery information available nahi hai.")
        state = "charging" if battery.power_plugged else "battery par"
        return ActionResult(
            True, f"Battery {int(battery.percent)} percent hai aur system {state} hai."
        )

    def screenshot(self, parameters: dict[str, Any]) -> ActionResult:
        import pyautogui

        folder = Path.home() / "Pictures" / "Aksh Screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"aksh-{datetime.now():%Y%m%d-%H%M%S}.png"
        pyautogui.screenshot(str(path))
        return ActionResult(True, "Screenshot save ho gaya.", {"path": str(path)})

    def set_volume(self, parameters: dict[str, Any]) -> ActionResult:
        import pyautogui

        value = max(0, min(100, int(float(parameters.get("value", 50)))))
        pyautogui.press("volumedown", presses=50, interval=0.01)
        pyautogui.press("volumeup", presses=round(value / 2), interval=0.01)
        return ActionResult(True, f"Volume approximately {value} percent set ho gaya.")

    def set_brightness(self, parameters: dict[str, Any]) -> ActionResult:
        value = max(0, min(100, int(float(parameters.get("value", 50)))))
        try:
            import screen_brightness_control as sbc

            sbc.set_brightness(value)
        except ImportError:
            return ActionResult(False, "Brightness dependency install nahi hai.")
        return ActionResult(True, f"Brightness {value} percent set ho gayi.")

    def system_action(self, parameters: dict[str, Any]) -> ActionResult:
        option = self.required(parameters, "option").lower()
        commands = {
            "shutdown": ["shutdown", "/s", "/t", "5"],
            "restart": ["shutdown", "/r", "/t", "5"],
            "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
            "sleep": [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Application]::SetSuspendState("
                "[System.Windows.Forms.PowerState]::Suspend,$false,$false)",
            ],
        }
        if option not in commands:
            return ActionResult(False, f"Unknown system action: {option}")
        subprocess.Popen(commands[option])
        messages = {
            "lock": "Computer lock kar raha hoon.",
            "sleep": "Computer sleep mode mein ja raha hai.",
        }
        message = messages.get(option, f"Computer 5 seconds mein {option} hoga.")
        return ActionResult(True, message)
