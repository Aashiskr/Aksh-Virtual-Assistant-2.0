from __future__ import annotations

import re
import threading
import urllib.parse
from pathlib import Path

from .models import Product


class FlipkartBrowser:
    def __init__(self, profile_dir: Path):
        self.profile_dir = profile_dir
        self.driver = None
        self.products: list[Product] = []
        self.index = -1
        self.query = ""
        self._lock = threading.RLock()

    @property
    def active(self) -> bool:
        return self.driver is not None and bool(self.products)

    def search(self, query: str) -> Product:
        with self._lock:
            driver = self._ensure_driver()
            self.query = query.strip()
            url = (
                "https://www.flipkart.com/search?q="
                + urllib.parse.quote_plus(self.query)
            )
            driver.get(url)
            self.products = self._collect_products()
            if not self.products:
                raise RuntimeError(
                    "Flipkart par usable products nahi mile. "
                    "Search ko thoda specific boliye."
                )
            self.index = 0
            return self._show_current()

    def refine(self, refinement: str) -> Product:
        base = self.query.strip()
        addition = self._clean_refinement(refinement)
        return self.search(" ".join(part for part in (base, addition) if part))

    def next(self) -> Product:
        with self._lock:
            self._require_session()
            if self.index + 1 >= len(self.products):
                raise RuntimeError("Is search ke aur products nahi bache.")
            self.index += 1
            return self._show_current()

    def previous(self) -> Product:
        with self._lock:
            self._require_session()
            if self.index <= 0:
                raise RuntimeError("Ye pehla product hai.")
            self.index -= 1
            return self._show_current()

    def select_size(self, size: str) -> str:
        from selenium.webdriver.common.by import By

        with self._lock:
            self._require_session()
            target = size.strip().upper()
            xpath = (
                "//*[self::button or self::a or @role='button']"
                f"[translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', "
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ')='{target}']"
            )
            for element in self.driver.find_elements(By.XPATH, xpath):
                if element.is_displayed() and element.is_enabled():
                    element.click()
                    return target
            raise RuntimeError(f"Size {target} is product par available nahi mili.")

    def add_current_to_cart(self) -> Product:
        from selenium.webdriver.common.by import By

        with self._lock:
            self._require_session()
            xpath = (
                "//*[self::button or @role='button']"
                "[contains(translate(normalize-space(.),"
                "'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),"
                "'ADD TO CART')]"
            )
            for button in self.driver.find_elements(By.XPATH, xpath):
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    return self.products[self.index]
            raise RuntimeError(
                "Add to cart button nahi mila. Size select ya Flipkart login "
                "required ho sakta hai."
            )

    def close(self) -> None:
        with self._lock:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
            self.driver = None
            self.products = []
            self.index = -1

    def current_report(self) -> str:
        self._require_session()
        return self.products[self.index].report(self.index, len(self.products))

    def _ensure_driver(self):
        if self.driver:
            try:
                _ = self.driver.current_url
                return self.driver
            except Exception:
                self.driver = None
        from selenium import webdriver

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument(f"--user-data-dir={self.profile_dir.resolve()}")
        options.add_argument("--disable-notifications")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.driver = webdriver.Chrome(options=options)
        return self.driver

    def _collect_products(self) -> list[Product]:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(self.driver, 18).until(
            lambda driver: driver.find_elements(
                By.CSS_SELECTOR, "a[href*='/p/']"
            )
        )
        products: list[Product] = []
        seen: set[str] = set()
        for link in self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/p/']"):
            try:
                href = (link.get_attribute("href") or "").strip()
                canonical = href.split("&lid=")[0]
                if not canonical or canonical in seen:
                    continue
                title = self._link_title(link, href)
                if not title:
                    continue
                seen.add(canonical)
                products.append(Product(title=title, url=href))
                if len(products) >= 40:
                    break
            except Exception:
                continue
        return products

    @staticmethod
    def _link_title(link, href: str) -> str:
        title = (link.get_attribute("title") or "").strip()
        title = title or (link.get_attribute("aria-label") or "").strip()
        link_text = link.text.strip()
        if not title and link_text:
            title = link_text.splitlines()[0]
        if not title:
            images = link.find_elements("tag name", "img")
            title = (images[0].get_attribute("alt") or "").strip() if images else ""
        if not title:
            slug = urllib.parse.urlparse(href).path.strip("/").split("/")[0]
            title = slug.replace("-", " ").title()
        return " ".join(title.split())[:180]

    def _show_current(self) -> Product:
        from selenium.webdriver.support.ui import WebDriverWait

        product = self.products[self.index]
        self.driver.get(product.url)
        WebDriverWait(self.driver, 15).until(
            lambda driver: driver.execute_script(
                "return document.readyState"
            )
            == "complete"
        )
        heading = self.driver.execute_script(
            "return (document.querySelector('h1')?.innerText || '').trim();"
        )
        if heading:
            product.title = " ".join(str(heading).split())[:180]
        price = self.driver.execute_script(
            """
            for (const element of document.querySelectorAll('div, span')) {
              const text = (element.textContent || '').trim();
              if (element.offsetParent !== null && /^₹\\s?[\\d,]+$/.test(text)) {
                return text;
              }
            }
            return '';
            """
        )
        match = re.search(r"₹\s?[\d,]+", str(price))
        product.price = match.group(0) if match else ""
        return product

    def _require_session(self) -> None:
        if not self.active or self.index < 0:
            raise RuntimeError("Pehle shopping search start kijiye.")

    @staticmethod
    def _clean_refinement(text: str) -> str:
        cleaned = re.sub(
            r"\b(?:dikhao|dikhana|search|dhundo|dhoondo|karo|kar do)\b",
            " ",
            text.casefold(),
        )
        return " ".join(cleaned.split())
