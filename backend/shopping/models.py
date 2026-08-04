from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Product:
    title: str
    url: str
    summary: str = ""
    price: str = ""

    def report(self, index: int, total: int) -> str:
        position = f"{index + 1} of {total}"
        details = f", {self.price}" if self.price else ""
        return f"Product {position}: {self.title}{details}."
