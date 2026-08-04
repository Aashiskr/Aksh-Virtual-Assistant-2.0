from __future__ import annotations

from .whatsapp_names import choose_contact_name
from .whatsapp_target import phone_targets_match


NON_CONTACT_ROWS = {
    "all",
    "chats",
    "contacts",
    "favourites",
    "groups in common",
    "messages",
}


def _is_contact_row(name: str) -> bool:
    normalized = " ".join(name.casefold().split())
    if not normalized or normalized in NON_CONTACT_ROWS:
        return False
    if normalized.startswith(("clear all", "unread ")):
        return False
    return "is also in this group" not in normalized


def _results_container(search):
    search_rect = search.rectangle()
    candidates = []
    for control in search.parent().children():
        if control.element_info.control_type != "Group":
            continue
        rect = control.rectangle()
        below_search = (
            rect.top >= search_rect.bottom
            and rect.left <= search_rect.left
            and rect.right <= search_rect.right + 100
            and rect.bottom - rect.top >= 24
        )
        if below_search:
            candidates.append(control)
    return (
        min(candidates, key=lambda control: control.rectangle().top)
        if candidates
        else search.parent()
    )


def _result_controls(container):
    frontier = [container]
    for _ in range(4):
        next_level = []
        for parent in frontier:
            children = parent.children()
            rows = [
                child
                for child in children
                if child.element_info.control_type in {"DataItem", "ListItem"}
            ]
            if rows:
                return rows
            next_level.extend(
                child
                for child in children
                if child.element_info.control_type
                in {"DataGrid", "Group", "List"}
            )
        frontier = next_level
    for control_type in ("DataItem", "ListItem", "Button", "Text"):
        controls = container.descendants(control_type=control_type)
        if controls:
            return controls
    return []


def find_contact_control(
    window,
    expected: str,
    search,
    *,
    prefer_first: bool = False,
):
    search_rect = search.rectangle()
    window_rect = window.rectangle()
    candidates: list[tuple[str, object]] = []
    seen: set[tuple[str, int, int, int, int]] = set()
    container = _results_container(search)
    for control in _result_controls(container):
        name = (control.element_info.name or "").strip()
        rect = control.rectangle()
        key = (name, rect.left, rect.top, rect.right, rect.bottom)
        inside_results = (
            rect.top >= search_rect.bottom - 5
            and rect.right <= search_rect.right + 80
            and rect.left >= window_rect.left
            and rect.bottom <= window_rect.bottom
            and rect.right > rect.left
            and rect.bottom > rect.top
            and control.is_visible()
        )
        if (
            name
            and _is_contact_row(name)
            and inside_results
            and key not in seen
        ):
            seen.add(key)
            candidates.append((name, control))
    candidates.sort(
        key=lambda item: (
            item[1].rectangle().top,
            item[1].rectangle().left,
        )
    )
    phone_matches = [
        control
        for name, control in candidates
        if phone_targets_match(expected, name)
    ]
    if phone_matches:
        return phone_matches[0]
    if any(character.isdigit() for character in expected):
        return None
    if prefer_first and candidates:
        return candidates[0][1]
    selected = choose_contact_name(
        expected, [name for name, _ in candidates]
    )
    if selected is None:
        return None
    return next(
        (control for name, control in candidates if name == selected),
        None,
    )
