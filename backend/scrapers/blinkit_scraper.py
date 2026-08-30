"""
blinkit_scraper.py — Mock scraper for Blinkit.

Simulates real scraper behaviour:
  • Prices seeded from product name → deterministic across calls
  • ±15 % price variance
  • Blinkit bias: cheaper on snacks, slightly pricier on dairy
  • ~5 % chance of "not found"
  • Async with httpx (actual call to Blinkit is mocked to avoid ToS issues)
"""

import hashlib
import random
from typing import List

from scrapers.base_scraper import BaseScraper, ProductResult
from config import APP_PRICE_BIAS, DELIVERY_CONFIG

# ---------------------------------------------------------------------------
# Base product catalogue with approximate INR prices
# ---------------------------------------------------------------------------
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
    """
    Derive a deterministic 'base price' from the product name + app name.
    Uses MD5 so the same input always produces the same price.
    """
    key = f"{name.lower().strip()}:{app}"
    digest = int(hashlib.md5(key.encode()).hexdigest(), 16)

    # Find the closest keyword in our catalogue
    name_lower = name.lower()
    base = _DEFAULT_BASE
    for kw, price in _BASE_PRICES.items():
        if kw in name_lower:
            base = price
            break

    # Derive a ±15 % variance deterministically
    rng = random.Random(digest)
    variance = rng.uniform(0.85, 1.15)
    return round(base * variance, 2)


def _apply_bias(price: float, category: str, app: str) -> float:
    bias = APP_PRICE_BIAS.get(app, {})
    multiplier = bias.get(category, bias.get("default", 1.0))
    return round(price * multiplier, 2)


def _not_found(name: str, app: str) -> bool:
    """5 % chance of not found, deterministic per (name, app)."""
    key = f"nf:{name.lower()}:{app}"
    digest = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return (digest % 100) < 5


class BlinkitScraper(BaseScraper):
    """Mock Blinkit scraper."""

    @property
    def app_name(self) -> str:
        return "blinkit"

    @property
    def app_url(self) -> str:
        return "https://blinkit.com"

    async def search_product(self, name: str, pincode: str) -> List[ProductResult]:
        """Return a list of mock product results for `name` on Blinkit."""
        if _not_found(name, self.app_name):
            return []

        price = _seed_price(name, self.app_name)
        # Determine category for bias
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

        # Blinkit shows a few variants; return top 3 deterministically
        rng = random.Random(int(hashlib.md5(name.encode()).hexdigest(), 16))
        results = [
            ProductResult(
                platform=self.app_name,
                product_id=f"bl_{abs(hash(name+str(i)))}",
                name=f"{name.title()} {rng.choice(['', '(Pack)', '- Fresh'])}".strip(),
                price=round(price * rng.uniform(0.98, 1.05), 2),
                unit="1 unit",
                in_stock=True,
            )
            for i in range(3)
        ]
        return results

    async def get_delivery_fee(self, pincode: str, cart_total: float) -> float:
        cfg = DELIVERY_CONFIG["blinkit"]
        return 0.0 if cart_total >= cfg["free_above"] else float(cfg["fee"])
