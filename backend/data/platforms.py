"""
platforms.py — Platform-specific product data and availability for GroceryAI.

Each platform has:
  • Base platform info (id, name, color, logo)
  • Per-product pricing variants (quantity, price, brand, availability)
  • Pincode coverage map
  • Delivery time estimates
  • Delivery fee config

Architecture note:
  This module is the "demo adapter" layer.
  Data is representative/demo data — not live prices.
  To integrate real APIs later, replace the functions below with real HTTP calls
  while keeping the same return shape.

  Each platform adapter exposes:
    get_product_url(platform_id, product_name, search_query) → str
    search_products() → via PLATFORM_PRODUCTS lookup
    get_product_comparison(product_id, pincode) → Dict

  Buy Now URLs use each platform's legitimate public search URL format.
  Direct product page URLs are NOT generated because we do not have real
  platform product IDs — doing so would produce broken 404 links.
  Search URLs are labelled as "Search on Platform" in the UI when no direct
  product URL is available.
"""

import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

DATA_TIMESTAMP = "2025-07-15"   # Demo data reference date

# ---------------------------------------------------------------------------
# Platform definitions
# ---------------------------------------------------------------------------
PLATFORMS: List[Dict[str, Any]] = [
    {
        "id": "zepto",
        "name": "Zepto",
        "short_name": "Zepto",
        "color": "#8B5CF6",
        "bg_color": "#F5F3FF",
        "website": "https://www.zeptonow.com",
        "search_url_template": "https://www.zeptonow.com/search?query={query}",
        "logo_emoji": "⚡",
        "tagline": "10 minutes delivery",
        "delivery_promise": "10–20 min",
        "free_delivery_above": 199,
        "delivery_fee": 25,
        "platform_fee": 3,
        "url_note": "Search URL — opens Zepto search for this product",
    },
    {
        "id": "blinkit",
        "name": "Blinkit",
        "short_name": "Blinkit",
        "color": "#F59E0B",
        "bg_color": "#FFFBEB",
        "website": "https://blinkit.com",
        "search_url_template": "https://blinkit.com/s/?q={query}",
        "logo_emoji": "💛",
        "tagline": "Blink and it's there",
        "delivery_promise": "10–15 min",
        "free_delivery_above": 149,
        "delivery_fee": 20,
        "platform_fee": 2,
        "url_note": "Search URL — opens Blinkit search for this product",
    },
    {
        "id": "instamart",
        "name": "Swiggy Instamart",
        "short_name": "Instamart",
        "color": "#F97316",
        "bg_color": "#FFF7ED",
        "website": "https://www.swiggy.com/instamart",
        "search_url_template": "https://www.swiggy.com/instamart/search?query={query}",
        "logo_emoji": "🟠",
        "tagline": "Delivered in 10 minutes",
        "delivery_promise": "15–30 min",
        "free_delivery_above": 299,
        "delivery_fee": 30,
        "platform_fee": 5,
        "url_note": "Search URL — opens Swiggy Instamart search for this product",
    },
    {
        "id": "flipkart",
        "name": "Flipkart Minutes",
        "short_name": "Fk Minutes",
        "color": "#2563EB",
        "bg_color": "#EFF6FF",
        "website": "https://www.flipkart.com/grocery",
        "search_url_template": "https://www.flipkart.com/search?q={query}&otracker=search&marketplace=GROCERY",
        "logo_emoji": "🔵",
        "tagline": "Grocery in minutes",
        "delivery_promise": "20–35 min",
        "free_delivery_above": 250,
        "delivery_fee": 35,
        "platform_fee": 4,
        "url_note": "Search URL — opens Flipkart Grocery search for this product",
    },
]

PLATFORM_BY_ID: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PLATFORMS}


def get_search_url(platform_id: str, query: str) -> str:
    """
    Return a legitimate platform search URL for a given product query.
    These are real search endpoints — not fake product pages.
    The UI should label these as 'Search on Platform' unless a direct
    product URL is available from the data source.
    """
    platform = PLATFORM_BY_ID.get(platform_id)
    if not platform:
        return ""
    import urllib.parse
    encoded = urllib.parse.quote_plus(query)
    return platform["search_url_template"].format(query=encoded)


# ---------------------------------------------------------------------------
# Pincode → platform availability
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
    if pincode in _METRO_PINCODES:
        return _METRO_PINCODES[pincode]
    h = int(hashlib.md5(pincode.encode()).hexdigest(), 16)
    # Deterministic but varied coverage for unknown pincodes
    slots = [(h >> i) & 0xFF for i in range(0, 32, 8)]
    return {
        "zepto":     slots[0] > 89,
        "blinkit":   slots[1] > 63,
        "instamart": slots[2] > 76,
        "flipkart":  slots[3] > 101,
    }


# ---------------------------------------------------------------------------
# Platform-specific product data
#
# Structure: PLATFORM_PRODUCTS[platform_id][product_id] = list of variants
# Each variant: {quantity, unit, price, mrp, brand, in_stock, search_query}
#
# search_query is used to build the Buy Now / Search URL for that variant.
# brand is the brand shown on that platform's listing.
# mrp is the maximum retail price (crossed-out original price) if available.
# ---------------------------------------------------------------------------

PLATFORM_PRODUCTS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {

    # ── ZEPTO ─────────────────────────────────────────────────────────────────
    "zepto": {
        "tomato":           [{"quantity": 250,  "unit": "g",   "price": 17,  "mrp": 20,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 32,  "mrp": 38,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 60,  "mrp": 72,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 114, "mrp": 136, "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 2kg"}],
        "potato":           [{"quantity": 1000, "unit": "g",   "price": 38,  "mrp": 45,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 72,  "mrp": 88,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 2kg"},
                             {"quantity": 5000, "unit": "g",   "price": 175, "mrp": 210, "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 5kg"}],
        "onion":            [{"quantity": 1000, "unit": "g",   "price": 44,  "mrp": 52,  "brand": "Farm Direct",       "in_stock": True,  "search_query": "onion 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 84,  "mrp": 100, "brand": "Farm Direct",       "in_stock": True,  "search_query": "onion 2kg"}],
        "carrot":           [{"quantity": 500,  "unit": "g",   "price": 28,  "mrp": 35,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh carrot 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 52,  "mrp": 65,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh carrot 1kg"}],
        "cucumber":         [{"quantity": 500,  "unit": "g",   "price": 20,  "mrp": 25,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh cucumber 500g"}],
        "capsicum":         [{"quantity": 250,  "unit": "g",   "price": 22,  "mrp": 28,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "green capsicum 250g"}],
        "spinach":          [{"quantity": 250,  "unit": "g",   "price": 14,  "mrp": 18,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh spinach 250g"}],
        "broccoli":         [{"quantity": 250,  "unit": "g",   "price": 25,  "mrp": 32,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh broccoli 250g"}],
        "brinjal":          [{"quantity": 500,  "unit": "g",   "price": 28,  "mrp": 35,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "brinjal eggplant 500g"}],
        "cauliflower":      [{"quantity": 1,    "unit": "pc",  "price": 40,  "mrp": 50,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "cauliflower whole"}],
        "apple":            [{"quantity": 1000, "unit": "g",   "price": 145, "mrp": 170, "brand": "Shimla Fresh",      "in_stock": True,  "search_query": "fresh apple 1kg"},
                             {"quantity": 500,  "unit": "g",   "price": 75,  "mrp": 88,  "brand": "Shimla Fresh",      "in_stock": True,  "search_query": "fresh apple 500g"}],
        "banana":           [{"quantity": 6,    "unit": "pcs", "price": 35,  "mrp": 42,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "banana 6 pieces"},
                             {"quantity": 12,   "unit": "pcs", "price": 68,  "mrp": 82,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "banana 12 pieces"}],
        "orange":           [{"quantity": 4,    "unit": "pcs", "price": 60,  "mrp": 72,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "orange fruits 4 pieces"}],
        "mango":            [{"quantity": 1000, "unit": "g",   "price": 255, "mrp": 300, "brand": "Ratnagiri",         "in_stock": True,  "search_query": "alphonso mango 1kg"}],
        "grapes":           [{"quantity": 500,  "unit": "g",   "price": 65,  "mrp": 80,  "brand": "Nashik Grapes",     "in_stock": True,  "search_query": "green grapes 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 125, "mrp": 155, "brand": "Nashik Grapes",     "in_stock": True,  "search_query": "green grapes 1kg"}],
        "watermelon":       [{"quantity": 1,    "unit": "pc",  "price": 79,  "mrp": 95,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "watermelon whole"}],
        "papaya":           [{"quantity": 1,    "unit": "pc",  "price": 55,  "mrp": 65,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "papaya fruit"}],
        "milk":             [{"quantity": 500,  "unit": "ml",  "price": 36,  "mrp": 36,  "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 500ml"},
                             {"quantity": 1000, "unit": "ml",  "price": 68,  "mrp": 68,  "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 1 litre"},
                             {"quantity": 2000, "unit": "ml",  "price": 132, "mrp": 136, "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 2 litre"}],
        "curd":             [{"quantity": 400,  "unit": "g",   "price": 22,  "mrp": 25,  "brand": "Amul",              "in_stock": True,  "search_query": "amul curd 400g"},
                             {"quantity": 1000, "unit": "g",   "price": 52,  "mrp": 58,  "brand": "Amul",              "in_stock": True,  "search_query": "amul curd 1kg"}],
        "paneer":           [{"quantity": 200,  "unit": "g",   "price": 72,  "mrp": 80,  "brand": "Amul",              "in_stock": True,  "search_query": "amul paneer 200g"},
                             {"quantity": 500,  "unit": "g",   "price": 175, "mrp": 195, "brand": "Amul",              "in_stock": True,  "search_query": "amul paneer 500g"}],
        "butter":           [{"quantity": 100,  "unit": "g",   "price": 55,  "mrp": 57,  "brand": "Amul",              "in_stock": True,  "search_query": "amul butter 100g"},
                             {"quantity": 500,  "unit": "g",   "price": 268, "mrp": 285, "brand": "Amul",              "in_stock": True,  "search_query": "amul butter 500g"}],
        "ghee":             [{"quantity": 500,  "unit": "ml",  "price": 320, "mrp": 355, "brand": "Amul",              "in_stock": True,  "search_query": "amul ghee 500ml"},
                             {"quantity": 1000, "unit": "ml",  "price": 620, "mrp": 695, "brand": "Amul",              "in_stock": True,  "search_query": "amul ghee 1 litre"}],
        "cheese":           [{"quantity": 200,  "unit": "g",   "price": 88,  "mrp": 96,  "brand": "Amul",              "in_stock": True,  "search_query": "amul processed cheese 200g"},
                             {"quantity": 400,  "unit": "g",   "price": 172, "mrp": 188, "brand": "Amul",              "in_stock": True,  "search_query": "amul processed cheese 400g"}],
        "yogurt":           [{"quantity": 90,   "unit": "g",   "price": 35,  "mrp": 40,  "brand": "Epigamia",          "in_stock": True,  "search_query": "epigamia greek yogurt 90g"},
                             {"quantity": 200,  "unit": "g",   "price": 65,  "mrp": 72,  "brand": "Epigamia",          "in_stock": True,  "search_query": "epigamia greek yogurt 200g"}],
        "rice":             [{"quantity": 1000, "unit": "g",   "price": 92,  "mrp": 105, "brand": "India Gate",        "in_stock": True,  "search_query": "india gate basmati rice 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 445, "mrp": 510, "brand": "India Gate",        "in_stock": True,  "search_query": "india gate basmati rice 5kg"}],
        "basmati_rice":     [{"quantity": 1000, "unit": "g",   "price": 105, "mrp": 118, "brand": "Daawat",            "in_stock": True,  "search_query": "daawat basmati rice 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 498, "mrp": 558, "brand": "Daawat",            "in_stock": True,  "search_query": "daawat basmati rice 5kg"}],
        "wheat":            [{"quantity": 1000, "unit": "g",   "price": 28,  "mrp": 32,  "brand": "Local Mandi",       "in_stock": True,  "search_query": "wheat grain 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 132, "mrp": 152, "brand": "Local Mandi",       "in_stock": True,  "search_query": "wheat grain 5kg"}],
        "atta":             [{"quantity": 1000, "unit": "g",   "price": 58,  "mrp": 65,  "brand": "Aashirvaad",        "in_stock": True,  "search_query": "aashirvaad atta 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 268, "mrp": 295, "brand": "Aashirvaad",        "in_stock": True,  "search_query": "aashirvaad atta 5kg"}],
        "toor_dal":         [{"quantity": 500,  "unit": "g",   "price": 68,  "mrp": 78,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "toor dal 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 135, "mrp": 155, "brand": "Tata Sampann",      "in_stock": True,  "search_query": "toor dal 1kg"}],
        "moong_dal":        [{"quantity": 500,  "unit": "g",   "price": 72,  "mrp": 85,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "moong dal 500g"}],
        "chana_dal":        [{"quantity": 500,  "unit": "g",   "price": 65,  "mrp": 78,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "chana dal 500g"}],
        "sugar":            [{"quantity": 1000, "unit": "g",   "price": 46,  "mrp": 50,  "brand": "Uttam",             "in_stock": True,  "search_query": "refined sugar 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 222, "mrp": 248, "brand": "Uttam",             "in_stock": True,  "search_query": "refined sugar 5kg"}],
        "salt":             [{"quantity": 1000, "unit": "g",   "price": 22,  "mrp": 24,  "brand": "Tata Salt",         "in_stock": True,  "search_query": "tata salt 1kg"}],
        "lays":             [{"quantity": 52,   "unit": "g",   "price": 20,  "mrp": 20,  "brand": "Lays",              "in_stock": True,  "search_query": "lays chips 52g"},
                             {"quantity": 78,   "unit": "g",   "price": 30,  "mrp": 30,  "brand": "Lays",              "in_stock": True,  "search_query": "lays chips 78g"}],
        "maggi":            [{"quantity": 70,   "unit": "g",   "price": 14,  "mrp": 14,  "brand": "Maggi",             "in_stock": True,  "search_query": "maggi noodles 70g"},
                             {"quantity": 280,  "unit": "g",   "price": 54,  "mrp": 56,  "brand": "Maggi",             "in_stock": True,  "search_query": "maggi noodles pack of 4"}],
        "britannia_biscuit":[{"quantity": 100,  "unit": "g",   "price": 30,  "mrp": 30,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia good day biscuit 100g"},
                             {"quantity": 200,  "unit": "g",   "price": 58,  "mrp": 60,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia good day biscuit 200g"}],
        "tata_tea":         [{"quantity": 250,  "unit": "g",   "price": 72,  "mrp": 80,  "brand": "Tata Tea",          "in_stock": True,  "search_query": "tata tea premium 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 140, "mrp": 158, "brand": "Tata Tea",          "in_stock": True,  "search_query": "tata tea premium 500g"}],
        "nescafe":          [{"quantity": 100,  "unit": "g",   "price": 220, "mrp": 235, "brand": "Nescafé",           "in_stock": True,  "search_query": "nescafe classic coffee 100g"}],
        "real_juice":       [{"quantity": 1000, "unit": "ml",  "price": 92,  "mrp": 99,  "brand": "Real",              "in_stock": True,  "search_query": "real fruit juice 1 litre"}],
        "dove_shampoo":     [{"quantity": 340,  "unit": "ml",  "price": 335, "mrp": 370, "brand": "Dove",              "in_stock": True,  "search_query": "dove intense repair shampoo 340ml"}],
        "colgate":          [{"quantity": 200,  "unit": "g",   "price": 78,  "mrp": 84,  "brand": "Colgate",           "in_stock": True,  "search_query": "colgate strong teeth toothpaste 200g"}],
        "surf_excel":       [{"quantity": 1000, "unit": "g",   "price": 130, "mrp": 145, "brand": "Surf Excel",        "in_stock": True,  "search_query": "surf excel easy wash 1kg"}],
        "vim":              [{"quantity": 500,  "unit": "ml",  "price": 99,  "mrp": 110, "brand": "Vim",               "in_stock": True,  "search_query": "vim dishwash liquid 500ml"}],
        "dettol_soap":      [{"quantity": 75,   "unit": "g",   "price": 38,  "mrp": 42,  "brand": "Dettol",            "in_stock": True,  "search_query": "dettol soap 75g"}],
        "lifebuoy_handwash":[{"quantity": 200,  "unit": "ml",  "price": 72,  "mrp": 80,  "brand": "Lifebuoy",          "in_stock": True,  "search_query": "lifebuoy handwash 200ml"}],
        "harpic":           [{"quantity": 500,  "unit": "ml",  "price": 99,  "mrp": 112, "brand": "Harpic",            "in_stock": True,  "search_query": "harpic floor cleaner 500ml"}],
        "tissue_box":       [{"quantity": 100,  "unit": "pcs", "price": 85,  "mrp": 95,  "brand": "Kleenex",           "in_stock": True,  "search_query": "tissue paper box 100 sheets"}],
        "eggs":             [{"quantity": 6,    "unit": "pcs", "price": 50,  "mrp": 56,  "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 6 pieces"},
                             {"quantity": 12,   "unit": "pcs", "price": 96,  "mrp": 108, "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 12 pieces"},
                             {"quantity": 30,   "unit": "pcs", "price": 228, "mrp": 255, "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 30 pieces"}],
        "chicken":          [{"quantity": 500,  "unit": "g",   "price": 175, "mrp": 195, "brand": "FreshToHome",       "in_stock": True,  "search_query": "chicken 500g fresh"},
                             {"quantity": 1000, "unit": "g",   "price": 338, "mrp": 385, "brand": "FreshToHome",       "in_stock": True,  "search_query": "chicken 1kg fresh"}],
        "fish":             [{"quantity": 500,  "unit": "g",   "price": 148, "mrp": 165, "brand": "FreshToHome",       "in_stock": True,  "search_query": "fresh fish fillet 500g"}],
        "bread":            [{"quantity": 400,  "unit": "g",   "price": 45,  "mrp": 50,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia bread 400g"}],
        "chocolate":        [{"quantity": 40,   "unit": "g",   "price": 20,  "mrp": 20,  "brand": "Dairy Milk",        "in_stock": True,  "search_query": "dairy milk chocolate 40g"},
                             {"quantity": 80,   "unit": "g",   "price": 40,  "mrp": 40,  "brand": "Dairy Milk",        "in_stock": True,  "search_query": "dairy milk chocolate 80g"}],
    },

    # ── BLINKIT ───────────────────────────────────────────────────────────────
    "blinkit": {
        "tomato":           [{"quantity": 250,  "unit": "g",   "price": 15,  "mrp": 18,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 29,  "mrp": 36,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 55,  "mrp": 68,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 105, "mrp": 128, "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 2kg"}],
        "potato":           [{"quantity": 1000, "unit": "g",   "price": 35,  "mrp": 42,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 67,  "mrp": 80,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 2kg"},
                             {"quantity": 5000, "unit": "g",   "price": 162, "mrp": 195, "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 5kg"}],
        "onion":            [{"quantity": 1000, "unit": "g",   "price": 42,  "mrp": 50,  "brand": "Farm Direct",       "in_stock": True,  "search_query": "onion 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 80,  "mrp": 96,  "brand": "Farm Direct",       "in_stock": True,  "search_query": "onion 2kg"}],
        "carrot":           [{"quantity": 500,  "unit": "g",   "price": 26,  "mrp": 32,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh carrot 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 48,  "mrp": 60,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh carrot 1kg"}],
        "cucumber":         [{"quantity": 500,  "unit": "g",   "price": 18,  "mrp": 24,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh cucumber 500g"}],
        "capsicum":         [{"quantity": 250,  "unit": "g",   "price": 20,  "mrp": 26,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "green capsicum 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 38,  "mrp": 48,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "green capsicum 500g"}],
        "spinach":          [{"quantity": 250,  "unit": "g",   "price": 12,  "mrp": 16,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh spinach 250g"}],
        "broccoli":         [{"quantity": 500,  "unit": "g",   "price": 45,  "mrp": 55,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh broccoli 500g"}],
        "brinjal":          [{"quantity": 500,  "unit": "g",   "price": 25,  "mrp": 32,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "brinjal eggplant 500g"}],
        "cauliflower":      [{"quantity": 1,    "unit": "pc",  "price": 38,  "mrp": 48,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "cauliflower whole"}],
        "apple":            [{"quantity": 500,  "unit": "g",   "price": 72,  "mrp": 85,  "brand": "Shimla Fresh",      "in_stock": True,  "search_query": "fresh apple 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 138, "mrp": 165, "brand": "Shimla Fresh",      "in_stock": True,  "search_query": "fresh apple 1kg"}],
        "banana":           [{"quantity": 6,    "unit": "pcs", "price": 32,  "mrp": 40,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "banana 6 pieces"},
                             {"quantity": 12,   "unit": "pcs", "price": 62,  "mrp": 78,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "banana 12 pieces"}],
        "orange":           [{"quantity": 4,    "unit": "pcs", "price": 58,  "mrp": 70,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "orange 4 pieces"}],
        "mango":            [{"quantity": 1000, "unit": "g",   "price": 248, "mrp": 295, "brand": "Ratnagiri",         "in_stock": True,  "search_query": "alphonso mango 1kg"}],
        "grapes":           [{"quantity": 500,  "unit": "g",   "price": 60,  "mrp": 75,  "brand": "Nashik Grapes",     "in_stock": True,  "search_query": "green grapes 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 115, "mrp": 145, "brand": "Nashik Grapes",     "in_stock": True,  "search_query": "green grapes 1kg"}],
        "watermelon":       [{"quantity": 1,    "unit": "pc",  "price": 75,  "mrp": 90,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "watermelon whole"}],
        "papaya":           [{"quantity": 1,    "unit": "pc",  "price": 52,  "mrp": 62,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "papaya fruit"}],
        "milk":             [{"quantity": 500,  "unit": "ml",  "price": 34,  "mrp": 34,  "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 500ml"},
                             {"quantity": 1000, "unit": "ml",  "price": 65,  "mrp": 65,  "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 1 litre"},
                             {"quantity": 2000, "unit": "ml",  "price": 128, "mrp": 130, "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 2 litre"}],
        "curd":             [{"quantity": 400,  "unit": "g",   "price": 20,  "mrp": 22,  "brand": "Amul",              "in_stock": True,  "search_query": "amul curd 400g"},
                             {"quantity": 1000, "unit": "g",   "price": 48,  "mrp": 52,  "brand": "Amul",              "in_stock": True,  "search_query": "amul curd 1kg"}],
        "paneer":           [{"quantity": 200,  "unit": "g",   "price": 68,  "mrp": 76,  "brand": "Amul",              "in_stock": True,  "search_query": "amul paneer 200g"},
                             {"quantity": 500,  "unit": "g",   "price": 168, "mrp": 188, "brand": "Amul",              "in_stock": True,  "search_query": "amul paneer 500g"}],
        "butter":           [{"quantity": 100,  "unit": "g",   "price": 52,  "mrp": 57,  "brand": "Amul",              "in_stock": True,  "search_query": "amul butter 100g"},
                             {"quantity": 500,  "unit": "g",   "price": 255, "mrp": 275, "brand": "Amul",              "in_stock": True,  "search_query": "amul butter 500g"}],
        "ghee":             [{"quantity": 500,  "unit": "ml",  "price": 308, "mrp": 345, "brand": "Amul",              "in_stock": True,  "search_query": "amul ghee 500ml"},
                             {"quantity": 1000, "unit": "ml",  "price": 598, "mrp": 678, "brand": "Amul",              "in_stock": True,  "search_query": "amul ghee 1 litre"}],
        "cheese":           [{"quantity": 200,  "unit": "g",   "price": 85,  "mrp": 96,  "brand": "Amul",              "in_stock": True,  "search_query": "amul processed cheese 200g"},
                             {"quantity": 400,  "unit": "g",   "price": 168, "mrp": 188, "brand": "Amul",              "in_stock": True,  "search_query": "amul processed cheese 400g"}],
        "yogurt":           [{"quantity": 90,   "unit": "g",   "price": 32,  "mrp": 38,  "brand": "Epigamia",          "in_stock": True,  "search_query": "epigamia greek yogurt 90g"},
                             {"quantity": 200,  "unit": "g",   "price": 62,  "mrp": 70,  "brand": "Epigamia",          "in_stock": True,  "search_query": "epigamia greek yogurt 200g"}],
        "rice":             [{"quantity": 1000, "unit": "g",   "price": 88,  "mrp": 100, "brand": "India Gate",        "in_stock": True,  "search_query": "india gate basmati rice 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 428, "mrp": 490, "brand": "India Gate",        "in_stock": True,  "search_query": "india gate basmati rice 5kg"}],
        "basmati_rice":     [{"quantity": 1000, "unit": "g",   "price": 99,  "mrp": 115, "brand": "Daawat",            "in_stock": True,  "search_query": "daawat basmati rice 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 475, "mrp": 548, "brand": "Daawat",            "in_stock": True,  "search_query": "daawat basmati rice 5kg"}],
        "wheat":            [{"quantity": 1000, "unit": "g",   "price": 26,  "mrp": 30,  "brand": "Local Mandi",       "in_stock": True,  "search_query": "wheat grain 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 124, "mrp": 145, "brand": "Local Mandi",       "in_stock": True,  "search_query": "wheat grain 5kg"}],
        "atta":             [{"quantity": 1000, "unit": "g",   "price": 52,  "mrp": 58,  "brand": "Aashirvaad",        "in_stock": True,  "search_query": "aashirvaad atta 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 255, "mrp": 285, "brand": "Aashirvaad",        "in_stock": True,  "search_query": "aashirvaad atta 5kg"}],
        "toor_dal":         [{"quantity": 500,  "unit": "g",   "price": 65,  "mrp": 75,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "toor dal 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 128, "mrp": 148, "brand": "Tata Sampann",      "in_stock": True,  "search_query": "toor dal 1kg"}],
        "moong_dal":        [{"quantity": 500,  "unit": "g",   "price": 68,  "mrp": 80,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "moong dal 500g"}],
        "chana_dal":        [{"quantity": 500,  "unit": "g",   "price": 62,  "mrp": 75,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "chana dal 500g"}],
        "sugar":            [{"quantity": 1000, "unit": "g",   "price": 44,  "mrp": 50,  "brand": "Uttam",             "in_stock": True,  "search_query": "refined sugar 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 212, "mrp": 245, "brand": "Uttam",             "in_stock": True,  "search_query": "refined sugar 5kg"}],
        "salt":             [{"quantity": 1000, "unit": "g",   "price": 20,  "mrp": 24,  "brand": "Tata Salt",         "in_stock": True,  "search_query": "tata salt 1kg"}],
        "lays":             [{"quantity": 52,   "unit": "g",   "price": 20,  "mrp": 20,  "brand": "Lays",              "in_stock": True,  "search_query": "lays chips 52g"},
                             {"quantity": 78,   "unit": "g",   "price": 30,  "mrp": 30,  "brand": "Lays",              "in_stock": True,  "search_query": "lays chips 78g"}],
        "maggi":            [{"quantity": 70,   "unit": "g",   "price": 14,  "mrp": 14,  "brand": "Maggi",             "in_stock": True,  "search_query": "maggi noodles 70g"},
                             {"quantity": 280,  "unit": "g",   "price": 53,  "mrp": 56,  "brand": "Maggi",             "in_stock": True,  "search_query": "maggi noodles pack of 4"}],
        "britannia_biscuit":[{"quantity": 100,  "unit": "g",   "price": 30,  "mrp": 30,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia good day biscuit 100g"},
                             {"quantity": 200,  "unit": "g",   "price": 58,  "mrp": 60,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia good day biscuit 200g"}],
        "tata_tea":         [{"quantity": 250,  "unit": "g",   "price": 70,  "mrp": 80,  "brand": "Tata Tea",          "in_stock": True,  "search_query": "tata tea premium 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 136, "mrp": 155, "brand": "Tata Tea",          "in_stock": True,  "search_query": "tata tea premium 500g"}],
        "nescafe":          [{"quantity": 100,  "unit": "g",   "price": 215, "mrp": 235, "brand": "Nescafe",           "in_stock": True,  "search_query": "nescafe classic coffee 100g"}],
        "real_juice":       [{"quantity": 1000, "unit": "ml",  "price": 88,  "mrp": 99,  "brand": "Real",              "in_stock": True,  "search_query": "real fruit juice 1 litre"}],
        "dove_shampoo":     [{"quantity": 340,  "unit": "ml",  "price": 328, "mrp": 370, "brand": "Dove",              "in_stock": True,  "search_query": "dove intense repair shampoo 340ml"}],
        "colgate":          [{"quantity": 200,  "unit": "g",   "price": 75,  "mrp": 84,  "brand": "Colgate",           "in_stock": True,  "search_query": "colgate strong teeth toothpaste 200g"}],
        "surf_excel":       [{"quantity": 1000, "unit": "g",   "price": 126, "mrp": 145, "brand": "Surf Excel",        "in_stock": True,  "search_query": "surf excel easy wash 1kg"}],
        "vim":              [{"quantity": 500,  "unit": "ml",  "price": 95,  "mrp": 110, "brand": "Vim",               "in_stock": True,  "search_query": "vim dishwash liquid 500ml"}],
        "dettol_soap":      [{"quantity": 75,   "unit": "g",   "price": 36,  "mrp": 42,  "brand": "Dettol",            "in_stock": True,  "search_query": "dettol soap 75g"}],
        "lifebuoy_handwash":[{"quantity": 200,  "unit": "ml",  "price": 70,  "mrp": 80,  "brand": "Lifebuoy",          "in_stock": True,  "search_query": "lifebuoy handwash 200ml"}],
        "harpic":           [{"quantity": 500,  "unit": "ml",  "price": 95,  "mrp": 112, "brand": "Harpic",            "in_stock": True,  "search_query": "harpic floor cleaner 500ml"}],
        "tissue_box":       [{"quantity": 100,  "unit": "pcs", "price": 82,  "mrp": 95,  "brand": "Kleenex",           "in_stock": True,  "search_query": "tissue paper box 100 sheets"}],
        "eggs":             [{"quantity": 6,    "unit": "pcs", "price": 48,  "mrp": 56,  "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 6 pieces"},
                             {"quantity": 12,   "unit": "pcs", "price": 92,  "mrp": 108, "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 12 pieces"},
                             {"quantity": 30,   "unit": "pcs", "price": 218, "mrp": 245, "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 30 pieces"}],
        "chicken":          [{"quantity": 500,  "unit": "g",   "price": 168, "mrp": 190, "brand": "FreshToHome",       "in_stock": True,  "search_query": "chicken 500g fresh"},
                             {"quantity": 1000, "unit": "g",   "price": 328, "mrp": 375, "brand": "FreshToHome",       "in_stock": True,  "search_query": "chicken 1kg fresh"}],
        "fish":             [{"quantity": 500,  "unit": "g",   "price": 142, "mrp": 162, "brand": "FreshToHome",       "in_stock": True,  "search_query": "fresh fish fillet 500g"}],
        "bread":            [{"quantity": 400,  "unit": "g",   "price": 43,  "mrp": 48,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia bread 400g"}],
        "chocolate":        [{"quantity": 40,   "unit": "g",   "price": 20,  "mrp": 20,  "brand": "Dairy Milk",        "in_stock": True,  "search_query": "dairy milk chocolate 40g"},
                             {"quantity": 80,   "unit": "g",   "price": 40,  "mrp": 40,  "brand": "Dairy Milk",        "in_stock": True,  "search_query": "dairy milk chocolate 80g"}],
    },

    # ── INSTAMART ─────────────────────────────────────────────────────────────
    "instamart": {
        "tomato":           [{"quantity": 250,  "unit": "g",   "price": 14,  "mrp": 17,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 28,  "mrp": 35,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 53,  "mrp": 65,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 1kg"}],
        "potato":           [{"quantity": 1000, "unit": "g",   "price": 36,  "mrp": 44,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 68,  "mrp": 84,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 2kg"}],
        "onion":            [{"quantity": 1000, "unit": "g",   "price": 45,  "mrp": 54,  "brand": "Farm Direct",       "in_stock": True,  "search_query": "onion 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 87,  "mrp": 105, "brand": "Farm Direct",       "in_stock": True,  "search_query": "onion 2kg"}],
        "carrot":           [{"quantity": 500,  "unit": "g",   "price": 25,  "mrp": 32,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh carrot 500g"}],
        "cucumber":         [{"quantity": 500,  "unit": "g",   "price": 19,  "mrp": 25,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh cucumber 500g"}],
        "capsicum":         [{"quantity": 250,  "unit": "g",   "price": 21,  "mrp": 27,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "green capsicum 250g"}],
        "spinach":          [{"quantity": 250,  "unit": "g",   "price": 13,  "mrp": 17,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh spinach 250g"}],
        "broccoli":         [{"quantity": 250,  "unit": "g",   "price": 22,  "mrp": 28,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh broccoli 250g"}],
        "brinjal":          [{"quantity": 500,  "unit": "g",   "price": 26,  "mrp": 33,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "brinjal eggplant 500g"}],
        "cauliflower":      [{"quantity": 1,    "unit": "pc",  "price": 42,  "mrp": 52,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "cauliflower whole"}],
        "apple":            [{"quantity": 1000, "unit": "g",   "price": 142, "mrp": 168, "brand": "Shimla Fresh",      "in_stock": True,  "search_query": "fresh apple 1kg"}],
        "banana":           [{"quantity": 6,    "unit": "pcs", "price": 34,  "mrp": 42,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "banana 6 pieces"},
                             {"quantity": 12,   "unit": "pcs", "price": 66,  "mrp": 82,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "banana 12 pieces"}],
        "orange":           [{"quantity": 4,    "unit": "pcs", "price": 55,  "mrp": 68,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "orange 4 pieces"}],
        "mango":            [{"quantity": 1000, "unit": "g",   "price": 252, "mrp": 298, "brand": "Ratnagiri",         "in_stock": True,  "search_query": "alphonso mango 1kg"}],
        "grapes":           [{"quantity": 500,  "unit": "g",   "price": 62,  "mrp": 78,  "brand": "Nashik Grapes",     "in_stock": True,  "search_query": "green grapes 500g"}],
        "watermelon":       [{"quantity": 1,    "unit": "pc",  "price": 72,  "mrp": 88,  "brand": "Fresh Farm",        "in_stock": False, "search_query": "watermelon whole"}],
        "papaya":           [{"quantity": 1,    "unit": "pc",  "price": 50,  "mrp": 60,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "papaya fruit"}],
        "milk":             [{"quantity": 1000, "unit": "ml",  "price": 70,  "mrp": 70,  "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 1 litre"},
                             {"quantity": 2000, "unit": "ml",  "price": 136, "mrp": 140, "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 2 litre"}],
        "curd":             [{"quantity": 400,  "unit": "g",   "price": 24,  "mrp": 26,  "brand": "Amul",              "in_stock": True,  "search_query": "amul curd 400g"},
                             {"quantity": 1000, "unit": "g",   "price": 58,  "mrp": 64,  "brand": "Amul",              "in_stock": True,  "search_query": "amul curd 1kg"}],
        "paneer":           [{"quantity": 200,  "unit": "g",   "price": 74,  "mrp": 82,  "brand": "Amul",              "in_stock": True,  "search_query": "amul paneer 200g"}],
        "butter":           [{"quantity": 100,  "unit": "g",   "price": 56,  "mrp": 57,  "brand": "Amul",              "in_stock": True,  "search_query": "amul butter 100g"}],
        "ghee":             [{"quantity": 500,  "unit": "ml",  "price": 325, "mrp": 360, "brand": "Amul",              "in_stock": True,  "search_query": "amul ghee 500ml"}],
        "cheese":           [{"quantity": 200,  "unit": "g",   "price": 90,  "mrp": 98,  "brand": "Amul",              "in_stock": True,  "search_query": "amul processed cheese 200g"}],
        "yogurt":           [{"quantity": 90,   "unit": "g",   "price": 36,  "mrp": 42,  "brand": "Epigamia",          "in_stock": True,  "search_query": "epigamia greek yogurt 90g"},
                             {"quantity": 200,  "unit": "g",   "price": 68,  "mrp": 76,  "brand": "Epigamia",          "in_stock": False, "search_query": "epigamia greek yogurt 200g"}],
        "rice":             [{"quantity": 1000, "unit": "g",   "price": 95,  "mrp": 108, "brand": "India Gate",        "in_stock": True,  "search_query": "india gate basmati rice 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 458, "mrp": 528, "brand": "India Gate",        "in_stock": True,  "search_query": "india gate basmati rice 5kg"}],
        "basmati_rice":     [{"quantity": 1000, "unit": "g",   "price": 108, "mrp": 120, "brand": "Daawat",            "in_stock": True,  "search_query": "daawat basmati rice 1kg"}],
        "wheat":            [{"quantity": 1000, "unit": "g",   "price": 27,  "mrp": 31,  "brand": "Local Mandi",       "in_stock": True,  "search_query": "wheat grain 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 128, "mrp": 148, "brand": "Local Mandi",       "in_stock": True,  "search_query": "wheat grain 5kg"}],
        "atta":             [{"quantity": 5000, "unit": "g",   "price": 272, "mrp": 298, "brand": "Aashirvaad",        "in_stock": True,  "search_query": "aashirvaad atta 5kg"}],
        "toor_dal":         [{"quantity": 1000, "unit": "g",   "price": 133, "mrp": 152, "brand": "Tata Sampann",      "in_stock": True,  "search_query": "toor dal 1kg"}],
        "moong_dal":        [{"quantity": 500,  "unit": "g",   "price": 70,  "mrp": 82,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "moong dal 500g"}],
        "chana_dal":        [{"quantity": 500,  "unit": "g",   "price": 64,  "mrp": 76,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "chana dal 500g"}],
        "sugar":            [{"quantity": 1000, "unit": "g",   "price": 47,  "mrp": 52,  "brand": "Uttam",             "in_stock": True,  "search_query": "refined sugar 1kg"}],
        "salt":             [{"quantity": 1000, "unit": "g",   "price": 23,  "mrp": 25,  "brand": "Tata Salt",         "in_stock": True,  "search_query": "tata salt 1kg"}],
        "lays":             [{"quantity": 52,   "unit": "g",   "price": 20,  "mrp": 20,  "brand": "Lays",              "in_stock": True,  "search_query": "lays chips 52g"}],
        "maggi":            [{"quantity": 70,   "unit": "g",   "price": 14,  "mrp": 14,  "brand": "Maggi",             "in_stock": True,  "search_query": "maggi noodles 70g"},
                             {"quantity": 280,  "unit": "g",   "price": 52,  "mrp": 56,  "brand": "Maggi",             "in_stock": True,  "search_query": "maggi noodles pack of 4"}],
        "britannia_biscuit":[{"quantity": 100,  "unit": "g",   "price": 32,  "mrp": 35,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia good day biscuit 100g"}],
        "tata_tea":         [{"quantity": 250,  "unit": "g",   "price": 74,  "mrp": 82,  "brand": "Tata Tea",          "in_stock": True,  "search_query": "tata tea premium 250g"}],
        "nescafe":          [{"quantity": 100,  "unit": "g",   "price": 218, "mrp": 235, "brand": "Nescafe",           "in_stock": True,  "search_query": "nescafe classic coffee 100g"}],
        "real_juice":       [{"quantity": 1000, "unit": "ml",  "price": 94,  "mrp": 99,  "brand": "Real",              "in_stock": True,  "search_query": "real fruit juice 1 litre"}],
        "dove_shampoo":     [{"quantity": 340,  "unit": "ml",  "price": 332, "mrp": 370, "brand": "Dove",              "in_stock": True,  "search_query": "dove intense repair shampoo 340ml"}],
        "colgate":          [{"quantity": 200,  "unit": "g",   "price": 80,  "mrp": 88,  "brand": "Colgate",           "in_stock": True,  "search_query": "colgate strong teeth toothpaste 200g"}],
        "surf_excel":       [{"quantity": 1000, "unit": "g",   "price": 132, "mrp": 148, "brand": "Surf Excel",        "in_stock": True,  "search_query": "surf excel easy wash 1kg"}],
        "vim":              [{"quantity": 500,  "unit": "ml",  "price": 102, "mrp": 115, "brand": "Vim",               "in_stock": True,  "search_query": "vim dishwash liquid 500ml"}],
        "dettol_soap":      [{"quantity": 75,   "unit": "g",   "price": 40,  "mrp": 44,  "brand": "Dettol",            "in_stock": True,  "search_query": "dettol soap 75g"}],
        "lifebuoy_handwash":[{"quantity": 200,  "unit": "ml",  "price": 75,  "mrp": 82,  "brand": "Lifebuoy",          "in_stock": True,  "search_query": "lifebuoy handwash 200ml"}],
        "harpic":           [{"quantity": 500,  "unit": "ml",  "price": 102, "mrp": 115, "brand": "Harpic",            "in_stock": True,  "search_query": "harpic floor cleaner 500ml"}],
        "tissue_box":       [{"quantity": 100,  "unit": "pcs", "price": 88,  "mrp": 99,  "brand": "Kleenex",           "in_stock": True,  "search_query": "tissue paper box 100 sheets"}],
        "eggs":             [{"quantity": 6,    "unit": "pcs", "price": 46,  "mrp": 54,  "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 6 pieces"},
                             {"quantity": 12,   "unit": "pcs", "price": 94,  "mrp": 108, "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 12 pieces"}],
        "chicken":          [{"quantity": 500,  "unit": "g",   "price": 172, "mrp": 195, "brand": "FreshToHome",       "in_stock": True,  "search_query": "chicken 500g fresh"}],
        "fish":             [{"quantity": 500,  "unit": "g",   "price": 155, "mrp": 175, "brand": "FreshToHome",       "in_stock": True,  "search_query": "fresh fish fillet 500g"}],
        "bread":            [{"quantity": 400,  "unit": "g",   "price": 46,  "mrp": 50,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia bread 400g"}],
        "chocolate":        [{"quantity": 40,   "unit": "g",   "price": 20,  "mrp": 20,  "brand": "Dairy Milk",        "in_stock": True,  "search_query": "dairy milk chocolate 40g"}],
    },

    # ── FLIPKART MINUTES ──────────────────────────────────────────────────────
    "flipkart": {
        "tomato":           [{"quantity": 250,  "unit": "g",   "price": 16,  "mrp": 20,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 33,  "mrp": 40,  "brand": "Fresh Farm",        "in_stock": False, "search_query": "fresh tomato 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 62,  "mrp": 75,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh tomato 1kg"}],
        "potato":           [{"quantity": 1000, "unit": "g",   "price": 40,  "mrp": 48,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 76,  "mrp": 92,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh potato 2kg"}],
        "onion":            [{"quantity": 1000, "unit": "g",   "price": 48,  "mrp": 58,  "brand": "Farm Direct",       "in_stock": True,  "search_query": "onion 1kg"},
                             {"quantity": 2000, "unit": "g",   "price": 92,  "mrp": 112, "brand": "Farm Direct",       "in_stock": True,  "search_query": "onion 2kg"}],
        "carrot":           [{"quantity": 500,  "unit": "g",   "price": 30,  "mrp": 37,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh carrot 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 56,  "mrp": 70,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh carrot 1kg"}],
        "cucumber":         [{"quantity": 500,  "unit": "g",   "price": 22,  "mrp": 28,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh cucumber 500g"}],
        "capsicum":         [{"quantity": 250,  "unit": "g",   "price": 24,  "mrp": 30,  "brand": "Fresh Farm",        "in_stock": False, "search_query": "green capsicum 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 45,  "mrp": 56,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "green capsicum 500g"}],
        "spinach":          [{"quantity": 250,  "unit": "g",   "price": 16,  "mrp": 20,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh spinach 250g"}],
        "broccoli":         [{"quantity": 250,  "unit": "g",   "price": 27,  "mrp": 34,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh broccoli 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 50,  "mrp": 62,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "fresh broccoli 500g"}],
        "brinjal":          [{"quantity": 500,  "unit": "g",   "price": 30,  "mrp": 38,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "brinjal eggplant 500g"}],
        "cauliflower":      [{"quantity": 1,    "unit": "pc",  "price": 45,  "mrp": 55,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "cauliflower whole"}],
        "apple":            [{"quantity": 500,  "unit": "g",   "price": 78,  "mrp": 90,  "brand": "Shimla Fresh",      "in_stock": True,  "search_query": "fresh apple 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 150, "mrp": 175, "brand": "Shimla Fresh",      "in_stock": True,  "search_query": "fresh apple 1kg"}],
        "banana":           [{"quantity": 6,    "unit": "pcs", "price": 38,  "mrp": 46,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "banana 6 pieces"},
                             {"quantity": 12,   "unit": "pcs", "price": 74,  "mrp": 90,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "banana 12 pieces"}],
        "orange":           [{"quantity": 4,    "unit": "pcs", "price": 62,  "mrp": 75,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "orange 4 pieces"}],
        "mango":            [{"quantity": 1000, "unit": "g",   "price": 260, "mrp": 308, "brand": "Ratnagiri",         "in_stock": True,  "search_query": "alphonso mango 1kg"}],
        "grapes":           [{"quantity": 500,  "unit": "g",   "price": 68,  "mrp": 82,  "brand": "Nashik Grapes",     "in_stock": True,  "search_query": "green grapes 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 130, "mrp": 158, "brand": "Nashik Grapes",     "in_stock": True,  "search_query": "green grapes 1kg"}],
        "watermelon":       [{"quantity": 1,    "unit": "pc",  "price": 82,  "mrp": 98,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "watermelon whole"}],
        "papaya":           [{"quantity": 1,    "unit": "pc",  "price": 58,  "mrp": 68,  "brand": "Fresh Farm",        "in_stock": True,  "search_query": "papaya fruit"}],
        "milk":             [{"quantity": 1000, "unit": "ml",  "price": 72,  "mrp": 72,  "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 1 litre"},
                             {"quantity": 2000, "unit": "ml",  "price": 140, "mrp": 144, "brand": "Amul",              "in_stock": True,  "search_query": "amul milk 2 litre"}],
        "curd":             [{"quantity": 400,  "unit": "g",   "price": 26,  "mrp": 28,  "brand": "Amul",              "in_stock": True,  "search_query": "amul curd 400g"},
                             {"quantity": 1000, "unit": "g",   "price": 62,  "mrp": 68,  "brand": "Amul",              "in_stock": True,  "search_query": "amul curd 1kg"}],
        "paneer":           [{"quantity": 200,  "unit": "g",   "price": 78,  "mrp": 85,  "brand": "Amul",              "in_stock": True,  "search_query": "amul paneer 200g"},
                             {"quantity": 500,  "unit": "g",   "price": 188, "mrp": 205, "brand": "Amul",              "in_stock": True,  "search_query": "amul paneer 500g"}],
        "butter":           [{"quantity": 100,  "unit": "g",   "price": 58,  "mrp": 60,  "brand": "Amul",              "in_stock": True,  "search_query": "amul butter 100g"},
                             {"quantity": 500,  "unit": "g",   "price": 278, "mrp": 300, "brand": "Amul",              "in_stock": True,  "search_query": "amul butter 500g"}],
        "ghee":             [{"quantity": 500,  "unit": "ml",  "price": 335, "mrp": 370, "brand": "Amul",              "in_stock": False, "search_query": "amul ghee 500ml"},
                             {"quantity": 1000, "unit": "ml",  "price": 648, "mrp": 718, "brand": "Amul",              "in_stock": True,  "search_query": "amul ghee 1 litre"}],
        "cheese":           [{"quantity": 200,  "unit": "g",   "price": 92,  "mrp": 100, "brand": "Amul",              "in_stock": True,  "search_query": "amul processed cheese 200g"},
                             {"quantity": 400,  "unit": "g",   "price": 178, "mrp": 196, "brand": "Amul",              "in_stock": False, "search_query": "amul processed cheese 400g"}],
        "yogurt":           [{"quantity": 90,   "unit": "g",   "price": 38,  "mrp": 44,  "brand": "Epigamia",          "in_stock": True,  "search_query": "epigamia greek yogurt 90g"},
                             {"quantity": 200,  "unit": "g",   "price": 70,  "mrp": 78,  "brand": "Epigamia",          "in_stock": True,  "search_query": "epigamia greek yogurt 200g"}],
        "rice":             [{"quantity": 1000, "unit": "g",   "price": 86,  "mrp": 98,  "brand": "India Gate",        "in_stock": True,  "search_query": "india gate basmati rice 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 415, "mrp": 475, "brand": "India Gate",        "in_stock": True,  "search_query": "india gate basmati rice 5kg"}],
        "basmati_rice":     [{"quantity": 1000, "unit": "g",   "price": 102, "mrp": 118, "brand": "Daawat",            "in_stock": True,  "search_query": "daawat basmati rice 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 488, "mrp": 558, "brand": "Daawat",            "in_stock": True,  "search_query": "daawat basmati rice 5kg"}],
        "wheat":            [{"quantity": 1000, "unit": "g",   "price": 29,  "mrp": 34,  "brand": "Local Mandi",       "in_stock": False, "search_query": "wheat grain 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 138, "mrp": 160, "brand": "Local Mandi",       "in_stock": True,  "search_query": "wheat grain 5kg"}],
        "atta":             [{"quantity": 1000, "unit": "g",   "price": 55,  "mrp": 62,  "brand": "Aashirvaad",        "in_stock": True,  "search_query": "aashirvaad atta 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 262, "mrp": 290, "brand": "Aashirvaad",        "in_stock": True,  "search_query": "aashirvaad atta 5kg"}],
        "toor_dal":         [{"quantity": 500,  "unit": "g",   "price": 67,  "mrp": 78,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "toor dal 500g"},
                             {"quantity": 1000, "unit": "g",   "price": 130, "mrp": 150, "brand": "Tata Sampann",      "in_stock": True,  "search_query": "toor dal 1kg"}],
        "moong_dal":        [{"quantity": 500,  "unit": "g",   "price": 72,  "mrp": 85,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "moong dal 500g"}],
        "chana_dal":        [{"quantity": 500,  "unit": "g",   "price": 66,  "mrp": 78,  "brand": "Tata Sampann",      "in_stock": True,  "search_query": "chana dal 500g"}],
        "sugar":            [{"quantity": 1000, "unit": "g",   "price": 45,  "mrp": 50,  "brand": "Uttam",             "in_stock": True,  "search_query": "refined sugar 1kg"},
                             {"quantity": 5000, "unit": "g",   "price": 218, "mrp": 242, "brand": "Uttam",             "in_stock": True,  "search_query": "refined sugar 5kg"}],
        "salt":             [{"quantity": 1000, "unit": "g",   "price": 21,  "mrp": 24,  "brand": "Tata Salt",         "in_stock": True,  "search_query": "tata salt 1kg"}],
        "lays":             [{"quantity": 52,   "unit": "g",   "price": 20,  "mrp": 20,  "brand": "Lays",              "in_stock": True,  "search_query": "lays chips 52g"},
                             {"quantity": 78,   "unit": "g",   "price": 30,  "mrp": 30,  "brand": "Lays",              "in_stock": True,  "search_query": "lays chips 78g"}],
        "maggi":            [{"quantity": 70,   "unit": "g",   "price": 14,  "mrp": 14,  "brand": "Maggi",             "in_stock": True,  "search_query": "maggi noodles 70g"},
                             {"quantity": 560,  "unit": "g",   "price": 104, "mrp": 112, "brand": "Maggi",             "in_stock": True,  "search_query": "maggi noodles pack of 8"}],
        "britannia_biscuit":[{"quantity": 100,  "unit": "g",   "price": 30,  "mrp": 30,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia good day biscuit 100g"},
                             {"quantity": 200,  "unit": "g",   "price": 62,  "mrp": 65,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia good day biscuit 200g"}],
        "tata_tea":         [{"quantity": 250,  "unit": "g",   "price": 73,  "mrp": 82,  "brand": "Tata Tea",          "in_stock": True,  "search_query": "tata tea premium 250g"},
                             {"quantity": 500,  "unit": "g",   "price": 142, "mrp": 160, "brand": "Tata Tea",          "in_stock": True,  "search_query": "tata tea premium 500g"}],
        "nescafe":          [{"quantity": 100,  "unit": "g",   "price": 222, "mrp": 238, "brand": "Nescafe",           "in_stock": True,  "search_query": "nescafe classic coffee 100g"}],
        "real_juice":       [{"quantity": 1000, "unit": "ml",  "price": 90,  "mrp": 99,  "brand": "Real",              "in_stock": True,  "search_query": "real fruit juice 1 litre"}],
        "dove_shampoo":     [{"quantity": 340,  "unit": "ml",  "price": 340, "mrp": 370, "brand": "Dove",              "in_stock": False, "search_query": "dove intense repair shampoo 340ml"}],
        "colgate":          [{"quantity": 200,  "unit": "g",   "price": 76,  "mrp": 84,  "brand": "Colgate",           "in_stock": True,  "search_query": "colgate strong teeth toothpaste 200g"}],
        "surf_excel":       [{"quantity": 1000, "unit": "g",   "price": 128, "mrp": 145, "brand": "Surf Excel",        "in_stock": True,  "search_query": "surf excel easy wash 1kg"}],
        "vim":              [{"quantity": 500,  "unit": "ml",  "price": 98,  "mrp": 112, "brand": "Vim",               "in_stock": True,  "search_query": "vim dishwash liquid 500ml"}],
        "dettol_soap":      [{"quantity": 75,   "unit": "g",   "price": 42,  "mrp": 46,  "brand": "Dettol",            "in_stock": True,  "search_query": "dettol soap 75g"}],
        "lifebuoy_handwash":[{"quantity": 200,  "unit": "ml",  "price": 78,  "mrp": 85,  "brand": "Lifebuoy",          "in_stock": True,  "search_query": "lifebuoy handwash 200ml"}],
        "harpic":           [{"quantity": 500,  "unit": "ml",  "price": 105, "mrp": 118, "brand": "Harpic",            "in_stock": True,  "search_query": "harpic floor cleaner 500ml"}],
        "tissue_box":       [{"quantity": 100,  "unit": "pcs", "price": 90,  "mrp": 99,  "brand": "Kleenex",           "in_stock": False, "search_query": "tissue paper box 100 sheets"}],
        "eggs":             [{"quantity": 6,    "unit": "pcs", "price": 50,  "mrp": 58,  "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 6 pieces"},
                             {"quantity": 12,   "unit": "pcs", "price": 98,  "mrp": 112, "brand": "Country Eggs",      "in_stock": True,  "search_query": "farm fresh eggs 12 pieces"}],
        "chicken":          [{"quantity": 500,  "unit": "g",   "price": 180, "mrp": 205, "brand": "FreshToHome",       "in_stock": True,  "search_query": "chicken 500g fresh"},
                             {"quantity": 1000, "unit": "g",   "price": 352, "mrp": 398, "brand": "FreshToHome",       "in_stock": True,  "search_query": "chicken 1kg fresh"}],
        "fish":             [{"quantity": 500,  "unit": "g",   "price": 158, "mrp": 178, "brand": "FreshToHome",       "in_stock": False, "search_query": "fresh fish fillet 500g"}],
        "bread":            [{"quantity": 400,  "unit": "g",   "price": 48,  "mrp": 52,  "brand": "Britannia",         "in_stock": True,  "search_query": "britannia bread 400g"}],
        "chocolate":        [{"quantity": 40,   "unit": "g",   "price": 20,  "mrp": 20,  "brand": "Dairy Milk",        "in_stock": True,  "search_query": "dairy milk chocolate 40g"},
                             {"quantity": 80,   "unit": "g",   "price": 40,  "mrp": 40,  "brand": "Dairy Milk",        "in_stock": True,  "search_query": "dairy milk chocolate 80g"}],
    },
}


# ---------------------------------------------------------------------------
# Normalised price calculation
# ---------------------------------------------------------------------------
def normalized_price(quantity: float, unit: str, price: float) -> Optional[float]:
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
# Public API functions
# ---------------------------------------------------------------------------

def get_product_comparison(product_id: str, pincode: str) -> Dict[str, Any]:
    """
    Return a full comparison object for a product across all platforms.
    Called by /api/product/{id}/compare endpoint.

    Buy Now URLs are legitimate platform search URLs, not fabricated product pages.
    The 'url_is_search' flag tells the frontend to label the button 'Search on Platform'
    instead of 'Buy Now' when only a search URL is available.
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
            })
            continue

        enriched_variants = []
        for v in variants:
            norm_p = normalized_price(v["quantity"], v["unit"], v["price"])
            norm_u = normalized_unit_label(v["unit"])
            search_q = v.get("search_query", product_id.replace("_", " "))
            product_url = get_search_url(pid, search_q)
            enriched_variants.append({
                **v,
                "normalized_price": norm_p,
                "normalized_unit": norm_u,
                "display_quantity": f"{v['quantity']}{v['unit']}",
                "product_url": product_url,
                "url_is_search": True,   # indicates this is a search URL, not direct product page
                "effective_available": v["in_stock"] and area_available,
                "last_updated": DATA_TIMESTAMP,
            })

        available_variants = [v for v in enriched_variants if v["effective_available"]]
        best = (
            min(available_variants, key=lambda x: x["normalized_price"] or 9999)
            if available_variants else None
        )

        platform_results.append({
            "platform": platform,
            "variants": enriched_variants,
            "best_variant": best,
            "area_available": area_available,
            "delivery_time": platform["delivery_promise"],
        })

    # Cheapest: only available best_variants
    available_bests = [r for r in platform_results if r["best_variant"] is not None]
    cheapest = None
    if available_bests:
        cheapest = min(available_bests, key=lambda r: r["best_variant"]["normalized_price"] or 9999)

    return {
        "product_id": product_id,
        "pincode": pincode,
        "platforms": platform_results,
        "cheapest_platform_id": cheapest["platform"]["id"] if cheapest else None,
        "data_note": f"Demo data - representative prices as of {DATA_TIMESTAMP}. Not live prices.",
    }


def check_availability(pincode: str) -> Dict[str, Any]:
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
