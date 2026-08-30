"""
aggregator.py — Coordinates scraping + matching for all apps in parallel.

For each supported app:
  1. Fan out product searches in parallel (asyncio.gather)
  2. Use the AI matcher to find the best product for each query item
  3. Sum prices and look up the delivery fee
  4. Return an AppPrice object per app
"""

import asyncio
import logging
from typing import List

from models.schemas import AppPrice, GroceryItem, ProductMatch
from scrapers.base_scraper import BaseScraper
from scrapers.blinkit_scraper import BlinkitScraper
from scrapers.zepto_scraper import ZeptoScraper
from scrapers.instamart_scraper import InstamartScraper
from scrapers.flipkart_scraper import FlipkartScraper
from ai import matcher as ai_matcher
from ai.matcher import build_query

logger = logging.getLogger(__name__)

# Registry of all available scrapers
_SCRAPERS: List[BaseScraper] = [
    BlinkitScraper(),
    ZeptoScraper(),
    InstamartScraper(),
    FlipkartScraper(),
]


async def _aggregate_single_app(
    scraper: BaseScraper,
    items: List[GroceryItem],
    pincode: str,
) -> AppPrice:
    """
    Run all searches for one app and assemble an AppPrice.
    Errors in individual product searches are caught so one failure
    doesn't block the whole app result.
    """
    matches: List[ProductMatch] = []
    items_missing: List[str] = []
    cart_subtotal = 0.0

    # Fan out all product searches for this app concurrently
    search_tasks = [
        scraper.search_product(build_query(item.brand, item.name), pincode)
        for item in items
    ]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    for item, candidates in zip(items, results):
        query = build_query(item.brand, item.name)

        if isinstance(candidates, Exception):
            logger.warning("[%s] search error for '%s': %s", scraper.app_name, query, candidates)
            candidates = []

        best, confidence = ai_matcher.best_match(query, candidates)

        if best is None:
            items_missing.append(item.raw)
            matches.append(ProductMatch(
                query=query,
                matched_name=None,
                price=0.0,
                confidence=0.0,
                found=False,
            ))
        else:
            cart_subtotal += best.price
            matches.append(ProductMatch(
                query=query,
                matched_name=best.name,
                price=best.price,
                confidence=confidence,
                found=True,
            ))

    # Get delivery fee based on subtotal (before fee)
    try:
        delivery_fee = await scraper.get_delivery_fee(pincode, cart_subtotal)
    except Exception as exc:
        logger.warning("[%s] delivery fee error: %s", scraper.app_name, exc)
        delivery_fee = 0.0

    total_price = round(cart_subtotal + delivery_fee, 2)
    items_found = sum(1 for m in matches if m.found)

    return AppPrice(
        app_name=scraper.app_name,
        total_price=total_price,
        delivery_fee=delivery_fee,
        items_found=items_found,
        items_missing=items_missing,
        url=scraper.app_url,
        matches=matches,
    )


async def aggregate_all(
    items: List[GroceryItem],
    pincode: str,
) -> List[AppPrice]:
    """
    Run all scrapers in parallel and return a list of AppPrice objects.
    Individual scraper failures are silently dropped (logged at WARNING).
    """
    tasks = [
        _aggregate_single_app(scraper, items, pincode)
        for scraper in _SCRAPERS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    app_prices: List[AppPrice] = []
    for scraper, result in zip(_SCRAPERS, results):
        if isinstance(result, Exception):
            logger.error("[%s] scraper failed entirely: %s", scraper.app_name, result)
        else:
            app_prices.append(result)

    return app_prices
