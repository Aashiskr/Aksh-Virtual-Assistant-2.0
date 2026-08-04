import tempfile
import unittest
from pathlib import Path

from backend.credentials import GroqKeyStore


class GroqKeyStoreTests(unittest.TestCase):
    def test_key_is_saved_only_in_protected_form(self):
        with tempfile.TemporaryDirectory() as folder:
            data_dir = Path(folder)
            store = GroqKeyStore(
                data_dir,
                protect=lambda value: b"protected:" + value[::-1],
                unprotect=lambda value: value.removeprefix(b"protected:")[::-1],
            )
            key = "gsk_" + ("x" * 32)
            store.save(key)
            raw = (data_dir / "groq_key.dat").read_bytes()
            self.assertNotIn(key.encode("utf-8"), raw)
            self.assertEqual(store.load(), key)


if __name__ == "__main__":
    unittest.main()
