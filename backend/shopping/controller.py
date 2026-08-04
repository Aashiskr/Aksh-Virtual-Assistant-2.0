from __future__ import annotations

import re
from typing import Any

from ..actions.base import ActionGroup
from ..models import ActionRequest, ActionResult
from .browser import FlipkartBrowser


class ShoppingActions(ActionGroup):
    def __init__(self, settings):
        super().__init__(settings)
        self.browser = FlipkartBrowser(
            settings.data_dir / "shopping_chrome_profile"
        )

    @property
    def active(self) -> bool:
        return self.browser.active

    def execute(self, parameters: dict[str, Any]) -> ActionResult:
        option = str(parameters.get("option", "search")).strip().casefold()
        query = str(parameters.get("query", "")).strip()
        handlers = {
            "search": lambda: self._search(query),
            "next": self._next,
            "previous": self._previous,
            "refine": lambda: self._refine(query),
            "size": lambda: self._size(query),
            "add_cart": self._add_cart,
            "stop": self._stop,
            "status": self._status,
        }
        handler = handlers.get(option)
        if not handler:
            return ActionResult(False, f"Unknown shopping option: {option}")
        return handler()

    def followup(self, text: str) -> ActionRequest | None:
        if not self.active:
            return None
        normalized = " ".join(text.casefold().split())
        if any(
            phrase in normalized
            for phrase in (
                "band karo",
                "nahi dekhna",
                "rehne do",
                "shopping stop",
                "frustrat",
                "bas karo",
            )
        ):
            return self._request("stop")
        if "cart" in normalized:
            return self._request("add_cart")
        if re.search(r"\b(?:pichla|previous|back wala)\b", normalized):
            return self._request("previous")
        if any(
            phrase in normalized
            for phrase in (
                "next",
                "nahi pasand",
                "nhi pasand",
                "aur dikhao",
                "dusra dikhao",
                "doosra dikhao",
            )
        ):
            return self._request("next")
        size = re.search(
            r"\b(?:size\s*)?(xxl|xl|xs|s|m|l|\d{1,2})\b", normalized
        )
        if size and ("size" in normalized or len(normalized.split()) <= 3):
            return self._request("size", size.group(1))
        if any(
            word in normalized
            for word in (
                "sasta",
                "mehnga",
                "black",
                "white",
                "blue",
                "red",
                "cotton",
                "oversized",
            )
        ):
            return self._request("refine", normalized)
        return None

    def close(self) -> None:
        self.browser.close()

    def _search(self, query: str) -> ActionResult:
        if not query:
            raise ValueError("Shopping ke liye product batayiye.")
        product = self.browser.search(query)
        return self._product_result(
            product,
            "Flipkart shopping start. "
            f"{self.browser.current_report()} Next ya cart bol sakte hain.",
        )

    def _next(self) -> ActionResult:
        product = self.browser.next()
        return self._product_result(
            product,
            "Ye wala dekhiye. "
            f"{self.browser.current_report()} Pasand na aaye to next boliye.",
        )

    def _previous(self) -> ActionResult:
        product = self.browser.previous()
        return self._product_result(
            product, f"Pichhla product: {self.browser.current_report()}"
        )

    def _refine(self, query: str) -> ActionResult:
        if not query:
            raise ValueError("Kaisa refinement chahiye?")
        product = self.browser.refine(query)
        return self._product_result(
            product, f"Search refine kar di. {self.browser.current_report()}"
        )

    def _size(self, query: str) -> ActionResult:
        selected = self.browser.select_size(query)
        return ActionResult(True, f"Size {selected} select kar diya.")

    def _add_cart(self) -> ActionResult:
        product = self.browser.add_current_to_cart()
        return self._product_result(
            product,
            f"{product.title} cart mein add kar diya. Checkout nahi kiya.",
        )

    def _stop(self) -> ActionResult:
        self.browser.close()
        return ActionResult(
            True,
            "Aww, shopping se frustrate ho gaye 😅 Chalo band kar di—"
            "baad mein fresh mood mein perfect wala dhundhenge.",
        )

    def _status(self) -> ActionResult:
        return ActionResult(True, self.browser.current_report())

    @staticmethod
    def _request(option: str, query: str = "") -> ActionRequest:
        return ActionRequest(
            "shopping", {"option": option, "query": query}
        )

    def _product_result(self, product, message: str) -> ActionResult:
        return ActionResult(
            True,
            message,
            {
                "title": product.title,
                "price": product.price,
                "url": product.url,
                "index": self.browser.index,
                "total": len(self.browser.products),
            },
        )
