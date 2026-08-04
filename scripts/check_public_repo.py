from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PARTS = {
    ".env",
    "archive",
    "build",
    "data",
    "dist",
    "logs",
    "node_modules",
    "private",
    "tmp",
}
FORBIDDEN_NAMES = {"local.properties", "wrangler.jsonc"}
FORBIDDEN_SUFFIXES = {".aab", ".apk", ".exe", ".jks", ".keystore"}
PATTERNS = {
    "Groq API key": re.compile(r"gsk_[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "private key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "local Windows user path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / value.decode("utf-8")
        for value in result.stdout.split(b"\0")
        if value
    ]


def main() -> int:
    violations: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT)
        lowered_parts = {part.casefold() for part in relative.parts}
        if FORBIDDEN_PARTS.intersection(lowered_parts):
            violations.append(f"forbidden tracked path: {relative}")
            continue
        if relative.name.casefold() in FORBIDDEN_NAMES:
            violations.append(f"machine/account-specific file: {relative}")
            continue
        if relative.suffix.casefold() in FORBIDDEN_SUFFIXES:
            violations.append(f"binary/signing artifact: {relative}")
            continue
        if not path.is_file() or path.stat().st_size > 2_500_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{label}: {relative}:{line}")

    if violations:
        print("Public repository guard failed:")
        print("\n".join(f"- {item}" for item in violations))
        return 1
    print("Public repository guard passed: no forbidden tracked secrets or files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
