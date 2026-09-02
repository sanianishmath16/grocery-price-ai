"""
platforms.py — Platform-specific product data and availability for GroceryAI.

Each platform has:
  • Base platform info (id, name, color, logo)
  • Per-product pricing variants (quantity, price, quality, availability)
  • Pincode coverage map
  • Delivery time estimates
  • Delivery fee config

Architecture note:
  This module is the "mock adapter" layer. To integrate real APIs later,
  replace the functions below with real HTTP calls while keeping
  the same return shape.
"""

import hashlib
import random
from typing import List, Dict, Any, Optional

# ---------------------------------------------------------------------------
# Platform definitions
# ---------------------------------------------------------------------------
PLATFORMS: List[Dict[str, Any]] = [
    {
        "id": "zepto",
        "name": "Zepto",
        "short_name": "Zepto",
        "color": "#8B5CF6",       # purple
        "bg_color": "#F5F3FF",
        "website": "https://www.zeptonow.com",
        "logo_emoji": "⚡",
        "tagline": "10 minutes delivery",
        "delivery_promise": "10–20 min",
        "free_delivery_above": 199,
        "delivery_fee": 25,
        "platform_fee": 3,
    },
    {
        "id": "blinkit",
        "name": "Blinkit",
        "short_name": "Blinkit",
        "color": "#F59E0B",       # yellow/amber
        "bg_color": "#FFFBEB",
        "website": "https://blinkit.com",
        "logo_emoji": "💛",
        "tagline": "Blink and it's there",
        "delivery_promise": "10–15 min",
        "free_delivery_above": 149,
        "delivery_fee": 20,
        "platform_fee": 2,
    },
    {
        "id": "instamart",
        "name": "Swiggy Instamart",
        "short_name": "Instamart",
        "color": "#F97316",       # orange
        "bg_color": "#FFF7ED",
        "website": "https://www.swiggy.com/instamart",
        "logo_emoji": "🟠",
        "tagline": "Delivered in 10 minutes",
        "delivery_promise": "15–30 min",
        "free_delivery_above": 299,
        "delivery_fee": 30,
        "platform_fee": 5,
    },
    {
        "id": "flipkart",
        "name": "Flipkart Minutes",
        "short_name": "Fk Minutes",
        "color": "#2563EB",       # blue
        "bg_color": "#EFF6FF",
        "website": "https://www.flipkart.com/grocery",
        "logo_emoji": "🔵",
        "tagline": "Grocery in minutes",
        "delivery_promise": "20–35 min",
        "free_delivery_above": 250,
        "delivery_fee": 35,
        "platform_fee": 4,
    },
]

PLATFORM_BY_ID: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PLATFORMS}

# ---------------------------------------------------------------------------
# Pincode → city / platform availability
#
# Format: { pincode: { platform_id: True/False } }
# Pincodes not in this dict → treated as "unavailable on all platforms"
# ---------------------------------------------------------------------------
_METRO_PINCODES = {
    # Chennai
    "600001": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "600002": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": False},
    "600004": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "600006": {"zepto": True,  "blinkit": False, "instamart": True,  "flipkart": False},
    "600017": {"zepto": True,  "blinkit": True,  "instamart": False, "flipkart": True},
    # Bangalore
    "560001": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "560002": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "560003": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": False},
    "560034": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "560078": {"zepto": True,  "blinkit": True,  "instamart": False, "flipkart": True},
    # Mumbai
    "400001": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "400002": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "400016": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "400050": {"zepto": False, "blinkit": True,  "instamart": True,  "flipkart": True},
    # Delhi
    "110001": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "110002": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "110011": {"zepto": True,  "blinkit": True,  "instamart": False, "flipkart": True},
    "110020": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    # Hyderabad
    "500001": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": False},
    "500034": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    # Pune
    "411001": {"zepto": True,  "blinkit": True,  "instamart": True,  "flipkart": True},
    "411014": {"zepto": True,  "blinkit": False, "instamart": True,  "flipkart": True},
    # Kolkata
    "700001": {"zepto": False, "blinkit": True,  "instamart": True,  "flipkart": True},
    "700013": {"zepto": False, "blinkit": True,  "instamart": False, "flipkart": True},
}

def _get_pincode_availability(pincode: str) -> Dict[str, bool]:
    """
    Return platform availability dict for a pincode.
    Unknown pincodes get a deterministic random result based on hash.
    """
    if pincode in _METRO_PINCODES:
        return _METRO_PINCODES[pincode]
    # For unknown pincodes, derive availability from hash (simulates partial coverage)
    h = int(hashlib.md5(pincode.encode()).hexdigest(), 16)
    r = random.Random(h)
    return {
        "zepto":     r.random() > 0.35,
        "blinkit":   r.random() > 0.25,
        "instamart": r.random() > 0.30,
        "flipkart":  r.random() > 0.40,
    }


# ---------------------------------------------------------------------------
# Platform-specific product data
#
# Structure: PLATFORM_PRODUCTS[platform_id][product_id] = list of variants
# Each variant: {quantity, unit, price, quality, in_stock, product_url}
# ---------------------------------------------------------------------------

def _url(platform_id: str, product_name: str) -> str:
    """Generate a placeholder deep-link URL."""
    slug = product_name.lower().replace(" ", "-")
    return f"{PLATFORM_BY_ID[platform_id]['website']}/search?q={slug}"


PLATFORM_PRODUCTS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {

    "zepto": {
        "tomato":           [{"quantity": 500, "unit": "g", "price": 32, "quality": "Premium", "in_stock": True},
                             {"quantity": 1000, "unit": "g", "price": 60, "quality": "Premium", "in_stock": True}],
        "potato":           [{"quantity": 1000, "unit": "g", "price": 38, "quality": "Regular", "in_stock": True},
                             {"quantity": 2000, "unit": "g", "price": 72, "quality": "Regular", "in_stock": True}],
        "onion":            [{"quantity": 1000, "unit": "g", "price": 44, "quality": "Regular", "in_stock": True}],
        "carrot":           [{"quantity": 500, "unit": "g", "price": 28, "quality": "Premium", "in_stock": True}],
        "cucumber":         [{"quantity": 500, "unit": "g", "price": 20, "quality": "Regular", "in_stock": True}],
        "capsicum":         [{"quantity": 250, "unit": "g", "price": 22, "quality": "Premium", "in_stock": True}],
        "spinach":          [{"quantity": 250, "unit": "g", "price": 14, "quality": "Premium", "in_stock": True}],
        "broccoli":         [{"quantity": 250, "unit": "g", "price": 25, "quality": "Premium", "in_stock": True}],
        "apple":            [{"quantity": 1000, "unit": "g", "price": 145, "quality": "Premium", "in_stock": True}],
        "banana":           [{"quantity": 6, "unit": "pcs", "price": 35, "quality": "Regular", "in_stock": True}],
        "mango":            [{"quantity": 1000, "unit": "g", "price": 255, "quality": "Premium", "in_stock": True}],
        "grapes":           [{"quantity": 500, "unit": "g", "price": 65, "quality": "Premium", "in_stock": True}],
        "watermelon":       [{"quantity": 1, "unit": "pc", "price": 79, "quality": "Regular", "in_stock": True}],
        "milk":             [{"quantity": 1000, "unit": "ml", "price": 68, "quality": "Full Cream", "in_stock": True},
                             {"quantity": 500, "unit": "ml", "price": 36, "quality": "Full Cream", "in_stock": True}],
        "curd":             [{"quantity": 400, "unit": "g", "price": 22, "quality": "Standard", "in_stock": True}],
        "paneer":           [{"quantity": 200, "unit": "g", "price": 72, "quality": "Fresh", "in_stock": True}],
        "butter":           [{"quantity": 100, "unit": "g", "price": 55, "quality": "Salted", "in_stock": True}],
        "ghee":             [{"quantity": 500, "unit": "ml", "price": 320, "quality": "Pure Cow", "in_stock": True}],
        "rice":             [{"quantity": 1000, "unit": "g", "price": 92, "quality": "Premium Basmati", "in_stock": True},
                             {"quantity": 5000, "unit": "g", "price": 445, "quality": "Premium Basmati", "in_stock": True}],
        "atta":             [{"quantity": 5000, "unit": "g", "price": 268, "quality": "Whole Wheat", "in_stock": True}],
        "toor_dal":         [{"quantity": 1000, "unit": "g", "price": 135, "quality": "Washed", "in_stock": True}],
        "sugar":            [{"quantity": 1000, "unit": "g", "price": 46, "quality": "Refined", "in_stock": True}],
        "salt":             [{"quantity": 1000, "unit": "g", "price": 22, "quality": "Iodised", "in_stock": True}],
        "lays":             [{"quantity": 52, "unit": "g", "price": 20, "quality": "Standard", "in_stock": True}],
        "maggi":            [{"quantity": 70, "unit": "g", "price": 14, "quality": "Standard", "in_stock": True},
                             {"quantity": 280, "unit": "g", "price": 54, "quality": "Pack of 4", "in_stock": True}],
        "britannia_biscuit":[{"quantity": 100, "unit": "g", "price": 30, "quality": "Standard", "in_stock": True}],
        "tata_tea":         [{"quantity": 250, "unit": "g", "price": 72, "quality": "Premium", "in_stock": True}],
        "nescafe":          [{"quantity": 100, "unit": "g", "price": 220, "quality": "Classic", "in_stock": True}],
        "real_juice":       [{"quantity": 1000, "unit": "ml", "price": 92, "quality": "Mixed Fruit", "in_stock": True}],
        "dove_shampoo":     [{"quantity": 340, "unit": "ml", "price": 335, "quality": "Intense Repair", "in_stock": True}],
        "colgate":          [{"quantity": 200, "unit": "g", "price": 78, "quality": "Strong Teeth", "in_stock": True}],
        "surf_excel":       [{"quantity": 1000, "unit": "g", "price": 130, "quality": "Easy Wash", "in_stock": True}],
        "vim":              [{"quantity": 500, "unit": "ml", "price": 99, "quality": "Lemon", "in_stock": True}],
        "eggs":             [{"quantity": 12, "unit": "pcs", "price": 96, "quality": "Farm Fresh", "in_stock": True}],
        "bread":            [{"quantity": 400, "unit": "g", "price": 45, "quality": "Soft", "in_stock": True}],
    },

    "blinkit": {
        "tomato":           [{"quantity": 1000, "unit": "g", "price": 55, "quality": "Regular", "in_stock": True},
                             {"quantity": 500,  "unit": "g", "price": 29, "quality": "Regular", "in_stock": True}],
        "potato":           [{"quantity": 1000, "unit": "g", "price": 35, "quality": "Regular", "in_stock": True},
                             {"quantity": 2000, "unit": "g", "price": 67, "quality": "Regular", "in_stock": True}],
        "onion":            [{"quantity": 1000, "unit": "g", "price": 42, "quality": "Regular", "in_stock": True}],
        "carrot":           [{"quantity": 500, "unit": "g", "price": 26, "quality": "Regular", "in_stock": True}],
        "cucumber":         [{"quantity": 500, "unit": "g", "price": 18, "quality": "Regular", "in_stock": True}],
        "capsicum":         [{"quantity": 250, "unit": "g", "price": 20, "quality": "Regular", "in_stock": True}],
        "spinach":          [{"quantity": 250, "unit": "g", "price": 12, "quality": "Regular", "in_stock": True}],
        "broccoli":         [{"quantity": 500, "unit": "g", "price": 45, "quality": "Regular", "in_stock": True}],
        "apple":            [{"quantity": 1000, "unit": "g", "price": 138, "quality": "Regular", "in_stock": True}],
        "banana":           [{"quantity": 6, "unit": "pcs", "price": 32, "quality": "Regular", "in_stock": True}],
        "mango":            [{"quantity": 1000, "unit": "g", "price": 248, "quality": "Regular", "in_stock": True}],
        "grapes":           [{"quantity": 500, "unit": "g", "price": 60, "quality": "Regular", "in_stock": True}],
        "watermelon":       [{"quantity": 1, "unit": "pc", "price": 75, "quality": "Regular", "in_stock": True}],
        "milk":             [{"quantity": 1000, "unit": "ml", "price": 65, "quality": "Full Cream", "in_stock": True},
                             {"quantity": 500, "unit": "ml", "price": 34, "quality": "Full Cream", "in_stock": True}],
        "curd":             [{"quantity": 400, "unit": "g", "price": 20, "quality": "Standard", "in_stock": True},
                             {"quantity": 1000, "unit": "g", "price": 48, "quality": "Standard", "in_stock": True}],
        "paneer":           [{"quantity": 200, "unit": "g", "price": 68, "quality": "Fresh", "in_stock": True}],
        "butter":           [{"quantity": 100, "unit": "g", "price": 52, "quality": "Salted", "in_stock": True},
                             {"quantity": 500, "unit": "g", "price": 255, "quality": "Salted", "in_stock": True}],
        "ghee":             [{"quantity": 500, "unit": "ml", "price": 308, "quality": "Pure Cow", "in_stock": True}],
        "rice":             [{"quantity": 1000, "unit": "g", "price": 88, "quality": "Basmati", "in_stock": True},
                             {"quantity": 5000, "unit": "g", "price": 428, "quality": "Basmati", "in_stock": True}],
        "atta":             [{"quantity": 5000, "unit": "g", "price": 255, "quality": "Whole Wheat", "in_stock": True}],
        "toor_dal":         [{"quantity": 1000, "unit": "g", "price": 128, "quality": "Washed", "in_stock": True}],
        "sugar":            [{"quantity": 1000, "unit": "g", "price": 44, "quality": "Refined", "in_stock": True}],
        "salt":             [{"quantity": 1000, "unit": "g", "price": 20, "quality": "Iodised", "in_stock": True}],
        "lays":             [{"quantity": 52, "unit": "g", "price": 20, "quality": "Standard", "in_stock": True},
                             {"quantity": 78, "unit": "g", "price": 30, "quality": "Standard", "in_stock": True}],
        "maggi":            [{"quantity": 70, "unit": "g", "price": 14, "quality": "Standard", "in_stock": True},
                             {"quantity": 280, "unit": "g", "price": 53, "quality": "Pack of 4", "in_stock": True}],
        "britannia_biscuit":[{"quantity": 200, "unit": "g", "price": 58, "quality": "Standard", "in_stock": True}],
        "tata_tea":         [{"quantity": 250, "unit": "g", "price": 70, "quality": "Premium", "in_stock": True}],
        "nescafe":          [{"quantity": 100, "unit": "g", "price": 215, "quality": "Classic", "in_stock": True}],
        "real_juice":       [{"quantity": 1000, "unit": "ml", "price": 88, "quality": "Mixed Fruit", "in_stock": True}],
        "dove_shampoo":     [{"quantity": 340, "unit": "ml", "price": 328, "quality": "Intense Repair", "in_stock": True}],
        "colgate":          [{"quantity": 200, "unit": "g", "price": 75, "quality": "Strong Teeth", "in_stock": True}],
        "surf_excel":       [{"quantity": 1000, "unit": "g", "price": 126, "quality": "Easy Wash", "in_stock": True}],
        "vim":              [{"quantity": 500, "unit": "ml", "price": 95, "quality": "Lemon", "in_stock": True}],
        "eggs":             [{"quantity": 12, "unit": "pcs", "price": 92, "quality": "Farm Fresh", "in_stock": True},
                             {"quantity": 6, "unit": "pcs", "price": 48, "quality": "Farm Fresh", "in_stock": True}],
        "bread":            [{"quantity": 400, "unit": "g", "price": 43, "quality": "Soft", "in_stock": True}],
    },

    "instamart": {
        "tomato":           [{"quantity": 500,  "unit": "g", "price": 28, "quality": "Premium", "in_stock": True},
                             {"quantity": 1000, "unit": "g", "price": 53, "quality": "Premium", "in_stock": True}],
        "potato":           [{"quantity": 1000, "unit": "g", "price": 36, "quality": "Regular", "in_stock": True}],
        "onion":            [{"quantity": 1000, "unit": "g", "price": 45, "quality": "Regular", "in_stock": True},
                             {"quantity": 2000, "unit": "g", "price": 87, "quality": "Regular", "in_stock": True}],
        "carrot":           [{"quantity": 500, "unit": "g", "price": 25, "quality": "Premium", "in_stock": True}],
        "cucumber":         [{"quantity": 500, "unit": "g", "price": 19, "quality": "Regular", "in_stock": True}],
        "capsicum":         [{"quantity": 250, "unit": "g", "price": 21, "quality": "Premium", "in_stock": True}],
        "spinach":          [{"quantity": 250, "unit": "g", "price": 13, "quality": "Fresh", "in_stock": True}],
        "broccoli":         [{"quantity": 250, "unit": "g", "price": 22, "quality": "Premium", "in_stock": True}],
        "apple":            [{"quantity": 1000, "unit": "g", "price": 142, "quality": "Premium", "in_stock": True}],
        "banana":           [{"quantity": 6, "unit": "pcs", "price": 34, "quality": "Regular", "in_stock": True}],
        "mango":            [{"quantity": 1000, "unit": "g", "price": 252, "quality": "Alphonso", "in_stock": True}],
        "grapes":           [{"quantity": 500, "unit": "g", "price": 62, "quality": "Seedless", "in_stock": True}],
        "watermelon":       [{"quantity": 1, "unit": "pc", "price": 72, "quality": "Regular", "in_stock": False}],
        "milk":             [{"quantity": 1000, "unit": "ml", "price": 70, "quality": "Toned", "in_stock": True}],
        "curd":             [{"quantity": 400, "unit": "g", "price": 24, "quality": "Standard", "in_stock": True}],
        "paneer":           [{"quantity": 200, "unit": "g", "price": 74, "quality": "Fresh", "in_stock": True}],
        "butter":           [{"quantity": 100, "unit": "g", "price": 56, "quality": "Salted", "in_stock": True}],
        "ghee":             [{"quantity": 500, "unit": "ml", "price": 325, "quality": "Pure Cow", "in_stock": True}],
        "rice":             [{"quantity": 1000, "unit": "g", "price": 95, "quality": "Basmati", "in_stock": True}],
        "atta":             [{"quantity": 5000, "unit": "g", "price": 272, "quality": "Whole Wheat", "in_stock": True}],
        "toor_dal":         [{"quantity": 1000, "unit": "g", "price": 133, "quality": "Washed", "in_stock": True}],
        "sugar":            [{"quantity": 1000, "unit": "g", "price": 47, "quality": "Refined", "in_stock": True}],
        "salt":             [{"quantity": 1000, "unit": "g", "price": 23, "quality": "Iodised", "in_stock": True}],
        "lays":             [{"quantity": 52, "unit": "g", "price": 20, "quality": "Standard", "in_stock": True}],
        "maggi":            [{"quantity": 70, "unit": "g", "price": 14, "quality": "Standard", "in_stock": True}],
        "britannia_biscuit":[{"quantity": 100, "unit": "g", "price": 32, "quality": "Standard", "in_stock": True}],
        "tata_tea":         [{"quantity": 250, "unit": "g", "price": 74, "quality": "Premium", "in_stock": True}],
        "nescafe":          [{"quantity": 100, "unit": "g", "price": 218, "quality": "Classic", "in_stock": True}],
        "real_juice":       [{"quantity": 1000, "unit": "ml", "price": 94, "quality": "Mixed Fruit", "in_stock": True}],
        "dove_shampoo":     [{"quantity": 340, "unit": "ml", "price": 332, "quality": "Intense Repair", "in_stock": True}],
        "colgate":          [{"quantity": 200, "unit": "g", "price": 80, "quality": "Strong Teeth", "in_stock": True}],
        "surf_excel":       [{"quantity": 1000, "unit": "g", "price": 132, "quality": "Easy Wash", "in_stock": True}],
        "vim":              [{"quantity": 500, "unit": "ml", "price": 102, "quality": "Lemon", "in_stock": True}],
        "eggs":             [{"quantity": 12, "unit": "pcs", "price": 94, "quality": "Farm Fresh", "in_stock": True}],
        "bread":            [{"quantity": 400, "unit": "g", "price": 46, "quality": "Soft", "in_stock": True}],
    },

    "flipkart": {
        "tomato":           [{"quantity": 1000, "unit": "g", "price": 62, "quality": "Regular", "in_stock": True},
                             {"quantity": 500,  "unit": "g", "price": 33, "quality": "Regular", "in_stock": False}],
        "potato":           [{"quantity": 1000, "unit": "g", "price": 40, "quality": "Regular", "in_stock": True}],
        "onion":            [{"quantity": 1000, "unit": "g", "price": 48, "quality": "Regular", "in_stock": True}],
        "carrot":           [{"quantity": 500, "unit": "g", "price": 30, "quality": "Regular", "in_stock": True}],
        "cucumber":         [{"quantity": 500, "unit": "g", "price": 22, "quality": "Regular", "in_stock": True}],
        "capsicum":         [{"quantity": 250, "unit": "g", "price": 24, "quality": "Regular", "in_stock": False}],
        "spinach":          [{"quantity": 250, "unit": "g", "price": 16, "quality": "Regular", "in_stock": True}],
        "broccoli":         [{"quantity": 250, "unit": "g", "price": 27, "quality": "Regular", "in_stock": True}],
        "apple":            [{"quantity": 1000, "unit": "g", "price": 150, "quality": "Regular", "in_stock": True}],
        "banana":           [{"quantity": 6, "unit": "pcs", "price": 38, "quality": "Regular", "in_stock": True}],
        "mango":            [{"quantity": 1000, "unit": "g", "price": 260, "quality": "Premium", "in_stock": True}],
        "grapes":           [{"quantity": 500, "unit": "g", "price": 68, "quality": "Regular", "in_stock": True}],
        "watermelon":       [{"quantity": 1, "unit": "pc", "price": 82, "quality": "Regular", "in_stock": True}],
        "milk":             [{"quantity": 1000, "unit": "ml", "price": 72, "quality": "Full Cream", "in_stock": True}],
        "curd":             [{"quantity": 400, "unit": "g", "price": 26, "quality": "Standard", "in_stock": True}],
        "paneer":           [{"quantity": 200, "unit": "g", "price": 78, "quality": "Fresh", "in_stock": True}],
        "butter":           [{"quantity": 100, "unit": "g", "price": 58, "quality": "Salted", "in_stock": True}],
        "ghee":             [{"quantity": 500, "unit": "ml", "price": 335, "quality": "Pure Cow", "in_stock": False}],
        "rice":             [{"quantity": 1000, "unit": "g", "price": 86, "quality": "Basmati", "in_stock": True}],
        "atta":             [{"quantity": 5000, "unit": "g", "price": 262, "quality": "Whole Wheat", "in_stock": True}],
        "toor_dal":         [{"quantity": 1000, "unit": "g", "price": 130, "quality": "Washed", "in_stock": True}],
        "sugar":            [{"quantity": 1000, "unit": "g", "price": 45, "quality": "Refined", "in_stock": True}],
        "salt":             [{"quantity": 1000, "unit": "g", "price": 21, "quality": "Iodised", "in_stock": True}],
        "lays":             [{"quantity": 52, "unit": "g", "price": 20, "quality": "Standard", "in_stock": True}],
        "maggi":            [{"quantity": 70, "unit": "g", "price": 14, "quality": "Standard", "in_stock": True},
                             {"quantity": 560, "unit": "g", "price": 104, "quality": "Pack of 8", "in_stock": True}],
        "britannia_biscuit":[{"quantity": 200, "unit": "g", "price": 62, "quality": "Standard", "in_stock": True}],
        "tata_tea":         [{"quantity": 250, "unit": "g", "price": 73, "quality": "Premium", "in_stock": True}],
        "nescafe":          [{"quantity": 100, "unit": "g", "price": 222, "quality": "Classic", "in_stock": True}],
        "real_juice":       [{"quantity": 1000, "unit": "ml", "price": 90, "quality": "Mixed Fruit", "in_stock": True}],
        "dove_shampoo":     [{"quantity": 340, "unit": "ml", "price": 340, "quality": "Intense Repair", "in_stock": False}],
        "colgate":          [{"quantity": 200, "unit": "g", "price": 76, "quality": "Strong Teeth", "in_stock": True}],
        "surf_excel":       [{"quantity": 1000, "unit": "g", "price": 128, "quality": "Easy Wash", "in_stock": True}],
        "vim":              [{"quantity": 500, "unit": "ml", "price": 98, "quality": "Lemon", "in_stock": True}],
        "eggs":             [{"quantity": 12, "unit": "pcs", "price": 98, "quality": "Farm Fresh", "in_stock": True}],
        "bread":            [{"quantity": 400, "unit": "g", "price": 48, "quality": "Soft", "in_stock": True}],
    },
}


# ---------------------------------------------------------------------------
# Mock price history (last 7 data points) for a product
# ---------------------------------------------------------------------------
def get_price_history(product_id: str, platform_id: str) -> List[Dict[str, Any]]:
    """Return last 7 days of mock price history for a product on a platform."""
    variants = PLATFORM_PRODUCTS.get(platform_id, {}).get(product_id, [])
    if not variants:
        return []
    current_price = variants[0]["price"]
    h = int(hashlib.md5(f"{product_id}:{platform_id}".encode()).hexdigest(), 16)
    rng = random.Random(h)
    history = []
    price = current_price
    days = ["6d ago", "5d ago", "4d ago", "3d ago", "2d ago", "Yesterday", "Today"]
    for day in days:
        delta = rng.uniform(-0.07, 0.07)
        price = round(max(price * (1 + delta), current_price * 0.80), 0)
        history.append({"day": day, "price": price})
    # Force last entry to current price
    history[-1]["price"] = current_price
    return history


# ---------------------------------------------------------------------------
# Normalised price calculation
# ---------------------------------------------------------------------------
def normalized_price(quantity: float, unit: str, price: float) -> Optional[float]:
    """
    Return price per base unit (₹/kg, ₹/L, ₹/piece).
    Returns None if unit cannot be normalised.
    """
    unit_lower = unit.lower().strip()
    if unit_lower in ("g", "gm", "gms", "gram", "grams"):
        return round(price / quantity * 1000, 2)
    elif unit_lower in ("kg", "kgs", "kilogram"):
        return round(price / quantity, 2)
    elif unit_lower in ("ml", "milliliter", "millilitre"):
        return round(price / quantity * 1000, 2)
    elif unit_lower in ("l", "liter", "litre", "liters", "litres"):
        return round(price / quantity, 2)
    elif unit_lower in ("pcs", "pc", "piece", "pieces", "nos"):
        return round(price / quantity, 2)
    return None


def normalized_unit_label(unit: str) -> str:
    unit_lower = unit.lower().strip()
    if unit_lower in ("g", "gm", "gms", "gram", "grams", "kg", "kgs", "kilogram"):
        return "kg"
    elif unit_lower in ("ml", "milliliter", "millilitre", "l", "liter", "litre", "liters", "litres"):
        return "L"
    elif unit_lower in ("pcs", "pc", "piece", "pieces", "nos"):
        return "pc"
    return unit


# ---------------------------------------------------------------------------
# Public API functions (the "adapter" interface)
# ---------------------------------------------------------------------------

def get_product_comparison(product_id: str, pincode: str) -> Dict[str, Any]:
    """
    Return a full comparison object for a product across all platforms.
    This is the core function called by the /api/product/{id}/compare endpoint.
    """
    pincode_avail = _get_pincode_availability(pincode)
    platform_results = []

    for platform in PLATFORMS:
        pid = platform["id"]
        area_available = pincode_avail.get(pid, False)
        variants = PLATFORM_PRODUCTS.get(pid, {}).get(product_id, [])

        if not variants:
            platform_results.append({
                "platform": platform,
                "variants": [],
                "best_variant": None,
                "area_available": area_available,
                "delivery_time": platform["delivery_promise"],
                "history": [],
            })
            continue

        enriched_variants = []
        for v in variants:
            norm_p = normalized_price(v["quantity"], v["unit"], v["price"])
            norm_u = normalized_unit_label(v["unit"])
            enriched_variants.append({
                **v,
                "normalized_price": norm_p,
                "normalized_unit": norm_u,
                "display_quantity": f"{v['quantity']}{v['unit']}",
                "product_url": _url(pid, product_id),
                "effective_available": v["in_stock"] and area_available,
            })

        # Best variant = lowest normalized price among in-stock items
        available_variants = [v for v in enriched_variants if v["effective_available"]]
        best = min(available_variants, key=lambda x: x["normalized_price"] or 9999) if available_variants else None

        history = get_price_history(product_id, pid)

        platform_results.append({
            "platform": platform,
            "variants": enriched_variants,
            "best_variant": best,
            "area_available": area_available,
            "delivery_time": platform["delivery_promise"],
            "history": history,
        })

    # Find cheapest overall (only consider available best_variants)
    available_bests = [
        r for r in platform_results
        if r["best_variant"] is not None
    ]
    cheapest = None
    if available_bests:
        cheapest = min(available_bests, key=lambda r: r["best_variant"]["normalized_price"] or 9999)

    return {
        "product_id": product_id,
        "pincode": pincode,
        "platforms": platform_results,
        "cheapest_platform_id": cheapest["platform"]["id"] if cheapest else None,
    }


def check_availability(pincode: str) -> Dict[str, Any]:
    """Return platform availability for a given pincode."""
    avail = _get_pincode_availability(pincode)
    return {
        "pincode": pincode,
        "platforms": [
            {
                "platform_id": pid,
                "platform_name": PLATFORM_BY_ID[pid]["name"],
                "available": avail.get(pid, False),
            }
            for pid in ["zepto", "blinkit", "instamart", "flipkart"]
        ],
    }
