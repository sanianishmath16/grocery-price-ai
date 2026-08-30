"""
base_scraper.py — Abstract base class that every platform scraper extends.

Provides:
  • A common interface (search_product, get_delivery_fee)
  • Shared httpx async client with headers rotation
  • Retry logic with exponential back-off
  • Rate-limiting guard (per-instance semaphore)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import httpx

from config import SCRAPER_TIMEOUT, SCRAPER_MAX_RETRIES, SCRAPER_RETRY_DELAY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data class returned by each scraper's search_product
# ---------------------------------------------------------------------------

class ProductResult:
    """A single product found on a platform."""

    def __init__(
        self,
        platform: str,
        product_id: str,
        name: str,
        price: float,
        unit: str = "",
        in_stock: bool = True,
        image_url: str = "",
    ):
        self.platform = platform
        self.product_id = product_id
        self.name = name
        self.price = price
        self.unit = unit
        self.in_stock = in_stock
        self.image_url = image_url

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProductResult {self.platform} | {self.name} | ₹{self.price}>"


# ---------------------------------------------------------------------------
# Rotating user-agent pool
# ---------------------------------------------------------------------------
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------

class BaseScraper(ABC):
    """
    All platform scrapers inherit from this class.

    Sub-classes must implement:
        search_product(name, pincode)  → list[ProductResult]
        get_delivery_fee(pincode, cart_total) → float
    """

    # Limit concurrent outgoing requests per scraper instance
    _CONCURRENCY = 3

    def __init__(self):
        self._semaphore = asyncio.Semaphore(self._CONCURRENCY)
        self._ua_index = 0

    # ------------------------------------------------------------------
    # Public interface (to be implemented by each platform)
    # ------------------------------------------------------------------

    @abstractmethod
    async def search_product(self, name: str, pincode: str) -> List[ProductResult]:
        """Search for a product by name on this platform."""
        ...

    @abstractmethod
    async def get_delivery_fee(self, pincode: str, cart_total: float) -> float:
        """Return the delivery fee for a given pincode and cart value."""
        ...

    @property
    @abstractmethod
    def app_name(self) -> str:
        """Canonical name for this platform (e.g. 'blinkit')."""
        ...

    @property
    @abstractmethod
    def app_url(self) -> str:
        """Homepage / app URL for this platform."""
        ...

    # ------------------------------------------------------------------
    # Shared HTTP helper
    # ------------------------------------------------------------------

    def _next_user_agent(self) -> str:
        ua = _USER_AGENTS[self._ua_index % len(_USER_AGENTS)]
        self._ua_index += 1
        return ua

    def _default_headers(self) -> dict:
        return {
            "User-Agent": self._next_user_agent(),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-IN,en;q=0.9",
        }

    async def _get(self, url: str, params: Optional[dict] = None) -> httpx.Response:
        """
        Perform a GET with retry logic and the shared semaphore.

        Raises httpx.HTTPError after all retries are exhausted.
        """
        async with self._semaphore:
            for attempt in range(1, SCRAPER_MAX_RETRIES + 2):
                try:
                    async with httpx.AsyncClient(timeout=SCRAPER_TIMEOUT) as client:
                        resp = await client.get(
                            url,
                            params=params,
                            headers=self._default_headers(),
                            follow_redirects=True,
                        )
                        resp.raise_for_status()
                        return resp
                except (httpx.HTTPError, httpx.TimeoutException) as exc:
                    if attempt > SCRAPER_MAX_RETRIES:
                        logger.warning(
                            "[%s] GET %s failed after %d retries: %s",
                            self.app_name, url, SCRAPER_MAX_RETRIES, exc,
                        )
                        raise
                    wait = SCRAPER_RETRY_DELAY * attempt
                    logger.debug("[%s] Retry %d in %.1fs", self.app_name, attempt, wait)
                    await asyncio.sleep(wait)
