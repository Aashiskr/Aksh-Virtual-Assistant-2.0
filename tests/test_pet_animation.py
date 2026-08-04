import unittest
from pathlib import Path

from PIL import Image

from frontend.desktop.pet_animation import (
    expression_for_state,
    motion_for_state,
)


ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "frontend" / "desktop" / "assets" / "expressions"


class PetAnimationTests(unittest.TestCase):
    def test_statuses_have_distinct_expressions(self):
        self.assertEqual(expression_for_state("listening", 0), "listening")
        self.assertEqual(expression_for_state("thinking", 0), "thinking")
        self.assertEqual(expression_for_state("working", 0), "working")
        self.assertEqual(expression_for_state("error", 0), "error")
        self.assertEqual(expression_for_state("sleeping", 0), "sleeping")

    def test_idle_periodically_changes_expression(self):
        self.assertEqual(expression_for_state("idle", 0), "idle")
        self.assertEqual(expression_for_state("idle", 95), "thinking")
        self.assertEqual(expression_for_state("idle", 125), "happy")

    def test_motion_profiles_are_bounded(self):
        for state in ("idle", "listening", "thinking", "working", "sleeping"):
            for tick in range(16):
                scale, offset, rotation = motion_for_state(state, tick)
                self.assertLessEqual(abs(scale), 3)
                self.assertLessEqual(abs(offset), 2)
                self.assertLessEqual(abs(rotation), 2)

    def test_expression_assets_have_real_transparency(self):
        for state in (
            "listening",
            "thinking",
            "working",
            "happy",
            "error",
            "sleeping",
        ):
            with self.subTest(state=state):
                image = Image.open(ASSET_DIR / f"aksh_{state}.png")
                self.assertEqual(image.mode, "RGBA")
                alpha = image.getchannel("A")
                self.assertEqual(alpha.getpixel((0, 0)), 0)
                self.assertIsNotNone(alpha.getbbox())


if __name__ == "__main__":
    unittest.main()
