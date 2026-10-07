from __future__ import annotations


PET_TOP_INSET = 10


def visible_pet_bounds(width: int, pet_size: int) -> tuple[int, int, int, int]:
    size = int(pet_size)
    left = (int(width) - size) // 2
    top = PET_TOP_INSET
    return left, top, left + size, top + size


def clamp_pet_position(
    x: int,
    y: int,
    *,
    screen_width: int,
    screen_height: int,
    screen_left: int = 0,
    screen_top: int = 0,
    window_width: int,
    window_height: int,
    pet_size: int,
) -> tuple[int, int]:
    left, top, right, bottom = visible_pet_bounds(window_width, pet_size)
    minimum_x = int(screen_left) - left
    maximum_x = int(screen_left) + int(screen_width) - right
    minimum_y = int(screen_top) - top
    maximum_y = int(screen_top) + int(screen_height) - max(bottom, window_height)
    return (
        max(minimum_x, min(maximum_x, int(x))),
        max(minimum_y, min(maximum_y, int(y))),
    )


def geometry_offset(x: int, y: int) -> str:
    return f"{int(x):+d}{int(y):+d}"
