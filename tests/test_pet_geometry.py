import unittest

from frontend.desktop.pet_geometry import (
    clamp_pet_position,
    geometry_offset,
    visible_pet_bounds,
)


class PetGeometryTests(unittest.TestCase):
    def test_small_pet_uses_visible_bounds_not_transparent_window(self):
        self.assertEqual(visible_pet_bounds(170, 96), (37, 10, 133, 106))
        self.assertEqual(
            clamp_pet_position(
                9999,
                9999,
                screen_width=1920,
                screen_height=1080,
                window_width=170,
                window_height=188,
                pet_size=96,
            ),
            (1787, 892),
        )

    def test_pet_can_reach_right_edge_on_offset_virtual_desktop(self):
        self.assertEqual(
            clamp_pet_position(
                9999,
                300,
                screen_width=3840,
                screen_height=1080,
                screen_left=-1920,
                screen_top=0,
                window_width=170,
                window_height=188,
                pet_size=96,
            ),
            (1787, 300),
        )

    def test_pet_can_reach_left_and_top_edges(self):
        self.assertEqual(
            clamp_pet_position(
                -999,
                -999,
                screen_width=1920,
                screen_height=1080,
                window_width=170,
                window_height=188,
                pet_size=96,
            ),
            (-37, -10),
        )

    def test_middle_position_is_unchanged(self):
        self.assertEqual(
            clamp_pet_position(
                400,
                300,
                screen_width=1920,
                screen_height=1080,
                window_width=170,
                window_height=188,
                pet_size=96,
            ),
            (400, 300),
        )

    def test_tk_geometry_offset_supports_negative_coordinates(self):
        self.assertEqual(geometry_offset(-37, 25), "-37+25")


if __name__ == "__main__":
    unittest.main()
