"""
schemas.py — Pydantic models for all API request/response shapes.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


# ---------------------------------------------------------------------------
# Inbound
# ---------------------------------------------------------------------------

class CompareRequest(BaseModel):
    """
    Request body for POST /api/compare.

    items    — plain-text grocery items, one per element.
               e.g. ["Amul Milk 1L", "Maggi 70g x5"]
    pincode  — 6-digit Indian pincode used to determine delivery area.
    """
    items: List[str] = Field(..., min_length=1, description="List of grocery items to compare")
    pincode: str = Field(..., pattern=r"^\d{6}$", description="6-digit delivery pincode")


# ---------------------------------------------------------------------------
# Normalised item (internal, exposed for debugging)
# ---------------------------------------------------------------------------

class GroceryItem(BaseModel):
    """Structured representation of a parsed grocery item."""
    raw: str                          # original string from the user
    brand: Optional[str] = None       # detected brand, if any
    name: str                         # cleaned product name
    quantity: Optional[float] = None  # numeric quantity
    unit: Optional[str] = None        # unit of measure (g, kg, L, ml, …)
    category: str = "default"         # coarse category for bias lookup


# ---------------------------------------------------------------------------
# Per-product match inside an app result
# ---------------------------------------------------------------------------

class ProductMatch(BaseModel):
    """How a single user item was resolved on a given app."""
    query: str                        # normalised query string
    matched_name: Optional[str]       # what the app called it (None = not found)
    price: float = 0.0                # unit price in INR
    confidence: float = 0.0          # matcher confidence 0–1
    found: bool = False


# ---------------------------------------------------------------------------
# Per-app outbound
# ---------------------------------------------------------------------------

class AppPrice(BaseModel):
    """
    Aggregated pricing for one app.

    total_price    — sum of matched item prices + delivery_fee
    delivery_fee   — platform delivery charge for this order
    items_found    — count of items that were matched
    items_missing  — list of item names that could not be found
    savings        — how much cheaper vs. the most expensive app (filled by ranker)
    url            — deep-link or homepage URL for the app
    matches        — per-item breakdown
    """
    app_name: str
    total_price: float
    delivery_fee: float
    items_found: int
    items_missing: List[str] = Field(default_factory=list)
    savings: float = 0.0
    url: str = ""
    matches: List[ProductMatch] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class CompareResponse(BaseModel):
    """
    Response from POST /api/compare.

    results       — list of AppPrice, sorted cheapest first
    savings_tip   — human-readable string highlighting the best deal
    query_items   — normalised items for transparency
    """
    results: List[AppPrice]
    savings_tip: str
    query_items: List[GroceryItem]


