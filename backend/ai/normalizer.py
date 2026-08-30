"""
normalizer.py — Rule-based NLP normalizer for grocery item strings.

Given a raw user string like "Amul Milk 1L" or "Maggi Noodles 70g x5",
returns a structured GroceryItem with brand, name, quantity, unit, and category.

No external API or ML model required — pure regex + lookup tables.
"""

import re
from typing import Optional, Tuple

from models.schemas import GroceryItem

# ---------------------------------------------------------------------------
# Known brand list (case-insensitive prefix match)
# ---------------------------------------------------------------------------
KNOWN_BRANDS = [
    "amul", "nestle", "britannia", "parle", "haldirams", "haldiram",
    "maggi", "lays", "uncle chipps", "kurkure", "bingo", "munch",
    "dairy milk", "cadbury", "kitkat", "kit kat", "5 star",
    "aashirvaad", "fortune", "saffola", "sundrop", "dabur", "patanjali",
    "himalaya", "dettol", "lifebuoy", "dove", "head & shoulders",
    "colgate", "pepsodent", "close up", "closeup", "vim", "surf excel",
    "ariel", "tide", "nirma", "rin", "tata", "mdh", "everest",
    "mother dairy", "nandini", "heritage",
]
# Sort longest first so multi-word brands match before single words
KNOWN_BRANDS.sort(key=len, reverse=True)

# ---------------------------------------------------------------------------
# Unit normalisation table
# ---------------------------------------------------------------------------
UNIT_MAP = {
    # volume
    "liter": "L", "litre": "L", "liters": "L", "litres": "L", "l": "L",
    "ml": "ml", "milliliter": "ml", "millilitre": "ml",
    # weight
    "kg": "kg", "kilogram": "kg", "kgs": "kg",
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "mg": "mg",
    # count
    "pcs": "pcs", "pc": "pcs", "piece": "pcs", "pieces": "pcs",
    "pack": "pack", "packs": "pack", "packet": "pack",
    "nos": "nos", "no": "nos",
}

# ---------------------------------------------------------------------------
# Category keywords
# ---------------------------------------------------------------------------
_CATEGORY_MAP = {
    "dairy":   ["milk", "curd", "butter", "cheese", "paneer", "ghee", "cream", "yogurt"],
    "snacks":  ["maggi", "noodle", "biscuit", "chips", "chocolate", "namkeen",
                "cookie", "wafer", "cracker", "candy"],
    "staples": ["rice", "dal", "lentil", "flour", "maida", "sugar", "salt",
                "oil", "atta", "poha", "semolina", "sooji"],
    "fruits":  ["apple", "banana", "mango", "orange", "grape", "tomato"],
    "veggies": ["onion", "potato", "carrot", "cabbage", "spinach", "brinjal"],
    "personal_care": ["shampoo", "soap", "toothpaste", "face wash", "moisturiser",
                      "conditioner", "detergent", "dishwash", "floor cleaner"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_brand(text: str) -> Tuple[Optional[str], str]:
    """
    Returns (brand, text_without_brand).
    Brand detection is case-insensitive and matched at any position.
    """
    text_lower = text.lower()
    for brand in KNOWN_BRANDS:
        if brand in text_lower:
            cleaned = re.sub(re.escape(brand), "", text_lower, flags=re.IGNORECASE).strip()
            return brand.title(), cleaned
    return None, text


def _detect_quantity_unit(text: str) -> Tuple[Optional[float], Optional[str], str]:
    """
    Searches for patterns like '1L', '200g', '2.5kg', '70gx5', '6 pcs'.
    Returns (quantity, unit, text_without_qty_unit).
    Also handles multipliers like 'x5' or '×3'.
    """
    # Pattern: optional number, optional multiplier, then qty+unit
    # e.g. "70g x5" → qty=70*5=350, unit=g
    # or "2 x 500ml" → qty=2*500=1000, unit=ml
    # Pattern 1: <number><unit> [x<multiplier>]
    pattern1 = re.compile(
        r"(\d+(?:\.\d+)?)\s*"          # base quantity
        r"([a-zA-Z]+)"                  # unit
        r"(?:\s*[xX×]\s*(\d+))?",      # optional x multiplier
        re.IGNORECASE,
    )
    # Pattern 2: <multiplier> x <number><unit>
    pattern2 = re.compile(
        r"(\d+)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)",
        re.IGNORECASE,
    )

    remainder = text

    # Try pattern 2 first
    m2 = pattern2.search(remainder)
    if m2:
        mult = float(m2.group(1))
        qty  = float(m2.group(2)) * mult
        raw_unit = m2.group(3).lower()
        unit = UNIT_MAP.get(raw_unit, raw_unit)
        remainder = remainder[: m2.start()] + remainder[m2.end():]
        return qty, unit, remainder.strip()

    # Try pattern 1
    m1 = pattern1.search(remainder)
    if m1:
        qty = float(m1.group(1))
        raw_unit = m1.group(2).lower()
        if raw_unit in UNIT_MAP or len(raw_unit) <= 3:
            unit = UNIT_MAP.get(raw_unit, raw_unit)
            if m1.group(3):
                qty *= float(m1.group(3))
            remainder = remainder[: m1.start()] + remainder[m1.end():]
            return qty, unit, remainder.strip()

    return None, None, remainder


def _detect_category(name: str) -> str:
    name_lower = name.lower()
    for cat, keywords in _CATEGORY_MAP.items():
        for kw in keywords:
            if kw in name_lower:
                return cat
    return "default"


def _clean_name(text: str) -> str:
    """Remove leftover punctuation and collapse spaces."""
    text = re.sub(r"[^a-zA-Z0-9 &'-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.title() if text else "Unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize(raw: str) -> GroceryItem:
    """
    Parse a raw grocery string into a structured GroceryItem.

    Examples
    --------
    >>> normalize("Amul Milk 1L")
    GroceryItem(raw='Amul Milk 1L', brand='Amul', name='Milk', quantity=1.0, unit='L', category='dairy')
    >>> normalize("Maggi Noodles 70g x5")
    GroceryItem(raw='Maggi Noodles 70g x5', brand='Maggi', name='Noodles', quantity=350.0, unit='g', category='snacks')
    """
    working = raw.strip()

    brand, working = _detect_brand(working)
    qty, unit, working = _detect_quantity_unit(working)
    name = _clean_name(working) or (brand or "Unknown")
    category = _detect_category(f"{brand or ''} {name}".lower())

    return GroceryItem(
        raw=raw,
        brand=brand,
        name=name,
        quantity=qty,
        unit=unit,
        category=category,
    )
