import tempfile
import unittest
from pathlib import Path

from backend.remote.credentials import PairingTokenStore


class PairingTokenStoreTests(unittest.TestCase):
    def test_plaintext_token_is_migrated_to_protected_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = root / "remote_token.txt"
            legacy.write_text("private-pairing-token", encoding="utf-8")
            store = PairingTokenStore(
                root,
                protect=lambda value: b"protected:" + value,
                unprotect=lambda value: value.removeprefix(b"protected:"),
            )
            self.assertEqual(
                store.load_or_create(),
                "private-pairing-token",
            )
            self.assertFalse(legacy.exists())
            self.assertEqual(
                (root / "remote_token.dat").read_bytes(),
                b"protected:private-pairing-token",
            )
            self.assertEqual(
                store.load_or_create(),
                "private-pairing-token",
            )


if __name__ == "__main__":
    unittest.main()
