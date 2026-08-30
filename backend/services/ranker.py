"""
ranker.py — Sorts AppPrice results and generates a human-readable savings tip.
"""

from typing import List

from models.schemas import AppPrice


def rank(app_prices: List[AppPrice]) -> List[AppPrice]:
    """
    Sort app prices ascending by total_price.
    Also fills in the `savings` field (vs. most expensive app).
    Returns the sorted list.
    """
    if not app_prices:
        return []

    sorted_prices = sorted(app_prices, key=lambda x: x.total_price)

    most_expensive = sorted_prices[-1].total_price
    for ap in sorted_prices:
        ap.savings = round(most_expensive - ap.total_price, 2)

    return sorted_prices


def savings_tip(ranked: List[AppPrice]) -> str:
    """
    Generate a concise tip string for the UI.

    Examples
    --------
    "Save ₹42.50 by ordering on Zepto instead of Instamart."
    "All apps have similar prices for your cart."
    """
    if not ranked:
        return "No results available."

    if len(ranked) == 1:
        return f"Only {ranked[0].app_name.title()} has your items available."

    cheapest  = ranked[0]
    priciest  = ranked[-1]
    diff      = priciest.total_price - cheapest.total_price

    if diff < 1.0:
        return "All apps have similar prices for your cart — go with the fastest!"

    pct = round(diff / priciest.total_price * 100, 1) if priciest.total_price else 0
    return (
        f"Save ₹{diff:.2f} ({pct}%) by ordering on "
        f"{cheapest.app_name.title()} instead of {priciest.app_name.title()}."
    )
