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
    window_width: int,
    pet_size: int,
) -> tuple[int, int]:
    left, top, right, bottom = visible_pet_bounds(window_width, pet_size)
    minimum_x = -left
    maximum_x = int(screen_width) - right
    minimum_y = -top
    maximum_y = int(screen_height) - bottom
    return (
        max(minimum_x, min(maximum_x, int(x))),
        max(minimum_y, min(maximum_y, int(y))),
    )


def geometry_offset(x: int, y: int) -> str:
    return f"{int(x):+d}{int(y):+d}"
