import tempfile
import unittest
from pathlib import Path

from frontend.desktop.first_run import _looks_like_groq_key, _save_environment_value


class FirstRunTests(unittest.TestCase):
    def test_groq_key_must_have_expected_prefix_and_length(self):
        self.assertTrue(_looks_like_groq_key("gsk_" + ("a" * 28)))
        self.assertFalse(_looks_like_groq_key("your_groq_api_key_here"))
        self.assertFalse(_looks_like_groq_key("gsk_short"))

    def test_save_key_preserves_other_environment_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text(
                "GROQ_API_KEY=old\nAKSH_OWNER_NAME=Riya\n",
                encoding="utf-8",
            )
            _save_environment_value(
                path, "GROQ_API_KEY", "gsk_" + ("b" * 28)
            )
            saved = path.read_text(encoding="utf-8")
        self.assertEqual(saved.count("GROQ_API_KEY="), 1)
        self.assertIn("AKSH_OWNER_NAME=Riya", saved)
        self.assertNotIn("GROQ_API_KEY=old", saved)


if __name__ == "__main__":
    unittest.main()
