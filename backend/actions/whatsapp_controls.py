from __future__ import annotations

from collections.abc import Iterable


def rect_tuple(control) -> tuple[int, int, int, int]:
    rect = control.rectangle()
    return rect.left, rect.top, rect.right, rect.bottom


def usable(control) -> bool:
    left, top, right, bottom = rect_tuple(control)
    return right > left and bottom > top and control.is_visible()


def find_edit(window, labels: Iterable[str], *, prefer_top: bool = False):
    controls = [
        control
        for control in window.descendants(control_type="Edit")
        if usable(control)
    ]
    for label in labels:
        target = label.casefold()
        for control in controls:
            name = (control.element_info.name or "").strip().casefold()
            if name == target or name.startswith(f"{target} "):
                return control
    if prefer_top and controls:
        return min(controls, key=lambda control: control.rectangle().top)
    return None


def find_button(window, labels: Iterable[str]):
    buttons = window.descendants(control_type="Button")
    for label in labels:
        target = label.casefold()
        for button in buttons:
            name = (button.element_info.name or "").strip().casefold()
            if (
                name == target or name.startswith(f"{target} ")
            ) and usable(button):
                return button
    return None
