import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from frontend.desktop.app import AkshPetApp, PET_SIZE_STEP


class PetSizeTests(unittest.TestCase):
    def make_app(self, size=178):
        app = object.__new__(AkshPetApp)
        app.settings = SimpleNamespace(pet_size=size)
        app.root = Mock()
        app.root.winfo_x.return_value = 20
        app.root.winfo_y.return_value = 30
        app.store = Mock()
        app.view = Mock()

        def resize(requested):
            app.settings.pet_size = max(96, min(320, int(requested)))

        app.view.set_pet_size.side_effect = resize
        return app

    def test_plus_increases_pet_by_one_step(self):
        app = self.make_app()
        app._adjust_pet_size(PET_SIZE_STEP)
        self.assertEqual(app.settings.pet_size, 194)
        app.store.update.assert_called_once_with(
            pet_size=194,
            pet_x=20,
            pet_y=30,
        )

    def test_minus_decreases_pet_by_one_step(self):
        app = self.make_app()
        app._adjust_pet_size(-PET_SIZE_STEP)
        self.assertEqual(app.settings.pet_size, 162)

    def test_persisted_size_uses_clamped_value(self):
        app = self.make_app(320)
        app._adjust_pet_size(PET_SIZE_STEP)
        app.store.update.assert_called_once_with(
            pet_size=320,
            pet_x=20,
            pet_y=30,
        )

    def test_microphone_menu_labels_show_on_off_icons(self):
        self.assertEqual(
            AkshPetApp._microphone_menu_label(True),
            "🎙  Microphone listening on",
        )
        self.assertEqual(
            AkshPetApp._microphone_menu_label(False),
            "🔇  Microphone listening off",
        )


if __name__ == "__main__":
    unittest.main()
