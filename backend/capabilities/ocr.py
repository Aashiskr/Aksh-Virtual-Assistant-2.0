from __future__ import annotations

import re
import shutil
from datetime import date, datetime
from pathlib import Path


DATE_PATTERN = re.compile(r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b")
PHONE_PATTERN = re.compile(r"(?<!\d)([6-9]\d{9})(?!\d)")


def extract_text(image_path: Path) -> str:
    import pytesseract
    from PIL import Image

    path = image_path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image file nahi mili: {path}")
    executable = shutil.which("tesseract")
    common = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    if executable:
        pytesseract.pytesseract.tesseract_cmd = executable
    elif common.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(common)
    else:
        raise RuntimeError("Tesseract OCR install nahi hai.")
    with Image.open(path) as image:
        return str(pytesseract.image_to_string(image)).strip()


def parse_identity_fields(raw_text: str) -> dict[str, str]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    fields: dict[str, str] = {}
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if "name" in lowered and ":" in line:
            value = line.split(":", 1)[1]
            if "father" not in lowered:
                fields.setdefault("name", _clean_name(value))
        elif "father" in lowered and index:
            fields.setdefault("name", _clean_name(lines[index - 1]))
        phone = PHONE_PATTERN.search(line.replace(" ", ""))
        if phone:
            fields.setdefault("phone", phone.group(1))
        if any(term in lowered for term in ("date of birth", "dob", "birth")):
            match = DATE_PATTERN.search(line)
            if match:
                fields["date_of_birth"] = match.group(1)
                age = _age_from_date(match.group(1))
                if age is not None:
                    fields["age"] = str(age)
    return {key: value for key, value in fields.items() if value}


def _clean_name(value: str) -> str:
    return " ".join(re.sub(r"[^A-Za-z .'-]", " ", value).split())


def _age_from_date(value: str) -> int | None:
    normalized = value.replace("/", "-").replace(".", "-")
    for pattern in ("%d-%m-%Y", "%d-%m-%y"):
        try:
            born = datetime.strptime(normalized, pattern).date()
            today = date.today()
            return today.year - born.year - (
                (today.month, today.day) < (born.month, born.day)
            )
        except ValueError:
            continue
    return None
