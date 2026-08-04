from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


class GroqKeyStore:
    """Stores a Groq API key encrypted for the current Windows account."""

    def __init__(
        self,
        data_dir: Path,
        *,
        protect: Callable[[bytes], bytes] | None = None,
        unprotect: Callable[[bytes], bytes] | None = None,
    ):
        self.path = data_dir / "groq_key.dat"
        self.protect = protect or _dpapi_protect
        self.unprotect = unprotect or _dpapi_unprotect

    def load(self) -> str:
        try:
            return self.unprotect(self.path.read_bytes()).decode("utf-8").strip()
        except (OSError, UnicodeError, ValueError):
            return ""

    def save(self, key: str) -> None:
        value = key.strip()
        if not value:
            raise ValueError("Groq API key empty nahi ho sakti.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(self.protect(value.encode("utf-8")))
        temporary.replace(self.path)


def _dpapi_protect(value: bytes) -> bytes:
    import win32crypt

    return win32crypt.CryptProtectData(
        value,
        "Aksh Groq API key",
        None,
        None,
        None,
        0,
    )


def _dpapi_unprotect(value: bytes) -> bytes:
    import win32crypt

    return win32crypt.CryptUnprotectData(
        value,
        None,
        None,
        None,
        0,
    )[1]
