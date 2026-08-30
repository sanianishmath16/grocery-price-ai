"""
zepto_scraper.py — Mock scraper for Zepto.

Zepto pricing quirks: cheaper on dairy, slightly pricier on snacks,
lowest free-delivery threshold (₹149).
"""

import hashlib
import random
from typing import List

from scrapers.base_scraper import BaseScraper, ProductResult
from config import APP_PRICE_BIAS, DELIVERY_CONFIG

_BASE_PRICES = {
    "milk": 68, "curd": 45, "butter": 55, "cheese": 120, "paneer": 90,
    "maggi": 14, "biscuit": 30, "chips": 20, "chocolate": 50, "namkeen": 40,
    "rice": 80, "dal": 100, "flour": 60, "sugar": 50, "salt": 20,
    "tomato": 30, "onion": 40, "potato": 35, "banana": 50, "apple": 120,
    "oil": 150, "ghee": 200, "honey": 180, "bread": 45, "egg": 75,
    "shampoo": 120, "soap": 35, "toothpaste": 55, "detergent": 90,
}
_DEFAULT_BASE = 60


def _seed_price(name: str, app: str) -> float:
    key = f"{name.lower().strip()}:{app}"
    digest = int(hashlib.md5(key.encode()).hexdigest(), 16)
    name_lower = name.lower()
    base = _DEFAULT_BASE
    for kw, price in _BASE_PRICES.items():
        if kw in name_lower:
            base = price
            break
    rng = random.Random(digest)
    return round(base * rng.uniform(0.85, 1.15), 2)


def _apply_bias(price: float, category: str, app: str) -> float:
    bias = APP_PRICE_BIAS.get(app, {})
    return round(price * bias.get(category, bias.get("default", 1.0)), 2)


def _not_found(name: str, app: str) -> bool:
    key = f"nf:{name.lower()}:{app}"
    digest = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return (digest % 100) < 5


class ZeptoScraper(BaseScraper):
    """Mock Zepto scraper."""

    @property
    def app_name(self) -> str:
        return "zepto"

    @property
    def app_url(self) -> str:
        return "https://www.zeptonow.com"

    async def search_product(self, name: str, pincode: str) -> List[ProductResult]:
        if _not_found(name, self.app_name):
            return []

        price = _seed_price(name, self.app_name)
        nl = name.lower()
        if any(w in nl for w in ("milk", "curd", "butter", "cheese", "paneer", "ghee")):
            category = "dairy"
        elif any(w in nl for w in ("maggi", "biscuit", "chips", "chocolate", "namkeen")):
            category = "snacks"
        elif any(w in nl for w in ("rice", "dal", "flour", "sugar", "salt", "oil")):
            category = "staples"
        else:
            category = "default"

        price = _apply_bias(price, category, self.app_name)

        rng = random.Random(int(hashlib.md5((name + "zepto").encode()).hexdigest(), 16))
        suffixes = ["", " - Zepto Fresh", " | Express"]
        results = [
            ProductResult(
                platform=self.app_name,
                product_id=f"zp_{abs(hash(name+str(i)))}",
                name=f"{name.title()}{rng.choice(suffixes)}",
                price=round(price * rng.uniform(0.97, 1.04), 2),
                unit="1 unit",
                in_stock=True,
            )
            for i in range(3)
        ]
        return results

    async def get_delivery_fee(self, pincode: str, cart_total: float) -> float:
        cfg = DELIVERY_CONFIG["zepto"]
        return 0.0 if cart_total >= cfg["free_above"] else float(cfg["fee"])
