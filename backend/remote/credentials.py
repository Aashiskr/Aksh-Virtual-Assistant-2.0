from __future__ import annotations

import secrets
from collections.abc import Callable
from pathlib import Path


class PairingTokenStore:
    """Stores the phone pairing token encrypted for the current Windows user."""

    def __init__(
        self,
        data_dir: Path,
        *,
        protect: Callable[[bytes], bytes] | None = None,
        unprotect: Callable[[bytes], bytes] | None = None,
    ):
        self.path = data_dir / "remote_token.dat"
        self.legacy_path = data_dir / "remote_token.txt"
        self.protect = protect or _dpapi_protect
        self.unprotect = unprotect or _dpapi_unprotect

    def load_or_create(self, override: str = "") -> str:
        if override.strip():
            return override.strip()
        token = self._read_protected() or self._read_legacy()
        if not token:
            token = secrets.token_urlsafe(32)
        self._save(token)
        if self.legacy_path.exists():
            self.legacy_path.unlink()
        return token

    def _read_protected(self) -> str:
        try:
            return self.unprotect(self.path.read_bytes()).decode("utf-8").strip()
        except (OSError, UnicodeError, ValueError):
            return ""

    def _read_legacy(self) -> str:
        try:
            return self.legacy_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _save(self, token: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(self.protect(token.encode("utf-8")))
        temporary.replace(self.path)


def _dpapi_protect(value: bytes) -> bytes:
    import win32crypt

    return win32crypt.CryptProtectData(
        value,
        "Aksh phone pairing token",
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
