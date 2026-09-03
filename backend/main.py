"""
main.py — FastAPI application entry point for GroceryAI v2.

Endpoints
---------
GET  /api/health                    — health check
GET  /api/apps                      — list supported platforms
GET  /api/categories                — list product categories
GET  /api/products                  — list all products (filterable by category)
GET  /api/product/{product_id}      — get a single product's details
GET  /api/product/{product_id}/compare — compare that product across all platforms
GET  /api/check-availability        — check platform availability for a pincode
GET  /api/platforms                 — list platform metadata
POST /api/compare                   — legacy text-based comparison (kept for compatibility)
"""

import logging
import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List, Any, Dict

from config import SUPPORTED_APPS, CORS_ORIGINS, MAX_IMAGE_SIZE_BYTES
from models.schemas import (
    CompareRequest, CompareResponse,
)
from ai.normalizer import normalize
from services import aggregator, ranker as ranker_svc
from cache import redis_cache
from data.products import CATEGORIES, PRODUCTS, PRODUCT_BY_ID, PRODUCTS_BY_CATEGORY
from data.platforms import (
    PLATFORMS, PLATFORM_BY_ID,
    get_product_comparison, check_availability,
)

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FRONTEND_CANDIDATES = [
    "/usr/share/nginx/html",
    os.path.join(_THIS_DIR, "..", "frontend"),
]
FRONTEND_DIR: str | None = next(
    (p for p in _FRONTEND_CANDIDATES if os.path.isfile(os.path.join(p, "index.html"))),
    None,
)

# ---------------------------------------------------------------------------
app = FastAPI(
    title="GroceryAI",
    description="Compare grocery prices across Blinkit, Zepto, Instamart and Flipkart Minutes.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Meta endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["meta"])
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/apps", tags=["meta"])
async def list_apps():
    return {"apps": SUPPORTED_APPS}


@app.get("/api/platforms", tags=["meta"])
async def list_platforms():
    """Return platform metadata (name, color, logo, etc.)."""
    return {"platforms": PLATFORMS}


# ---------------------------------------------------------------------------
# Catalogue endpoints
# ---------------------------------------------------------------------------

@app.get("/api/categories", tags=["catalogue"])
async def list_categories():
    """Return all grocery categories."""
    return {"categories": CATEGORIES}


@app.get("/api/products", tags=["catalogue"])
async def list_products(
    category: Optional[str] = Query(None, description="Filter by category id"),
    q: Optional[str] = Query(None, description="Search query"),
    brand: Optional[str] = Query(None, description="Filter by brand name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List products, optionally filtered by category, brand and/or search query.
    Supports pagination via limit/offset.
    """
    if category:
        products = PRODUCTS_BY_CATEGORY.get(category, [])
    else:
        products = list(PRODUCTS)  # copy to allow filtering

    if brand:
        brand_lower = brand.lower()
        products = [p for p in products if brand_lower in p.get("brand", "").lower()]

    if q:
        q_lower = q.lower()
        products = [
            p for p in products
            if q_lower in p["name"].lower()
            or q_lower in p["id"].lower()
            or q_lower in p.get("brand", "").lower()
            or any(q_lower in tag.lower() for tag in p.get("tags", []))
            or q_lower in p.get("subcategory", "").lower()
            or q_lower in p.get("category", "").lower()
        ]

    total = len(products)
    paginated = products[offset: offset + limit]
    return {"products": paginated, "total": total, "offset": offset, "limit": limit}


@app.get("/api/brands", tags=["catalogue"])
async def list_brands():
    """Return all unique brands in the catalogue with product count."""
    brand_map: dict = {}
    for p in PRODUCTS:
        brand = p.get("brand", "")
        if not brand:
            continue
        if brand not in brand_map:
            brand_map[brand] = {"name": brand, "count": 0, "categories": set()}
        brand_map[brand]["count"] += 1
        brand_map[brand]["categories"].add(p.get("category", ""))
    # Convert sets to lists for JSON serialisation
    brands = [
        {"name": b, "count": d["count"], "categories": list(d["categories"])}
        for b, d in sorted(brand_map.items(), key=lambda x: x[1]["count"], reverse=True)
    ]
    return {"brands": brands}


@app.get("/api/product/{product_id}", tags=["catalogue"])
async def get_product(product_id: str):
    """Get detailed info for a single product."""
    product = PRODUCT_BY_ID.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")
    return {"product": product}


@app.get("/api/product/{product_id}/compare", tags=["compare"])
async def compare_product(
    product_id: str,
    pincode: str = Query(..., pattern=r"^\d{6}$", description="6-digit delivery pincode"),
):
    """
    Compare a specific product across all platforms for a given pincode.

    Returns platform-specific pricing, quantity, quality, availability,
    delivery time, and price history. Identifies the cheapest option
    using normalized price (₹/kg, ₹/L, ₹/pc).
    """
    if product_id not in PRODUCT_BY_ID:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")

    result = get_product_comparison(product_id, pincode)
    return result


@app.get("/api/check-availability", tags=["availability"])
async def check_pincode_availability(
    pincode: str = Query(..., pattern=r"^\d{6}$", description="6-digit delivery pincode"),
):
    """
    Check which platforms deliver to the given pincode.
    """
    return check_availability(pincode)


# ---------------------------------------------------------------------------
# Legacy text-based compare (kept for backward compatibility)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Data Import endpoint
# ---------------------------------------------------------------------------

@app.post("/api/import/products", tags=["import"])
async def import_products(products: List[Dict[str, Any]] = Body(...)):
    """
    Import products from a JSON array.
    Each product must have at minimum: id, name, brand, category.
    Returns count of successfully imported products.
    
    This endpoint adds products to the in-memory catalog (restart clears them).
    For persistent storage, write to products.py or use a database.
    """
    from data.products import PRODUCTS, PRODUCT_BY_ID, PRODUCTS_BY_CATEGORY
    imported = 0
    skipped = 0
    for p in products:
        if not all(k in p for k in ("id", "name", "brand", "category")):
            skipped += 1
            continue
        if p["id"] not in PRODUCT_BY_ID:
            PRODUCTS.append(p)
            PRODUCT_BY_ID[p["id"]] = p
            PRODUCTS_BY_CATEGORY.setdefault(p["category"], []).append(p)
            imported += 1
        else:
            skipped += 1
    return {"imported": imported, "skipped": skipped, "total": len(PRODUCTS)}


@app.get("/api/import/template", tags=["import"])
async def import_template():
    """Return a CSV template and JSON example for bulk product import."""
    csv_headers = [
        "id", "name", "brand", "category", "subcategory", "description",
        "image_url", "available_sizes", "base_unit", "base_price_inr",
        "tags", "emoji", "rating"
    ]
    example_product = {
        "id": "example_product_1",
        "name": "Example Atta Brand 5kg",
        "brand": "Example Brand",
        "category": "staples",
        "subcategory": "Atta & Flour",
        "description": "Premium whole wheat atta for soft rotis.",
        "image_url": "https://example.com/product-image.jpg",
        "available_sizes": ["1kg", "5kg", "10kg"],
        "base_unit": "kg",
        "base_price_inr": 55,
        "tags": ["staple", "atta", "flour", "wheat"],
        "emoji": "🌾",
        "rating": 4.5
    }
    return {
        "csv_headers": csv_headers,
        "json_example": [example_product],
        "note": "POST the JSON array to /api/import/products to import. Platform pricing can be added via /api/import/platform-products.",
        "supported_categories": [c["id"] for c in CATEGORIES],
    }


@app.post("/api/compare", response_model=CompareResponse, tags=["compare"])
async def compare_prices(body: CompareRequest):
    """
    Compare grocery prices across all supported apps (legacy text-based endpoint).
    """
    if not body.items:
        raise HTTPException(status_code=422, detail="items list must not be empty")

    cache_key = redis_cache.make_key("compare", body.items, body.pincode)
    cached = await redis_cache.get_cached(cache_key)
    if cached:
        return CompareResponse(**cached)

    normalised = [normalize(item) for item in body.items]
    app_prices = await aggregator.aggregate_all(normalised, body.pincode)

    if not app_prices:
        raise HTTPException(status_code=503, detail="All scrapers failed. Please try again later.")

    ranked = ranker_svc.rank(app_prices)
    tip = ranker_svc.savings_tip(ranked)
    response = CompareResponse(results=ranked, savings_tip=tip, query_items=normalised)

    await redis_cache.set_cached(cache_key, response.model_dump())
    return response


# ---------------------------------------------------------------------------
# Frontend static files
# ---------------------------------------------------------------------------
if FRONTEND_DIR:
    logger.info("Serving frontend from: %s", FRONTEND_DIR)

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    logger.warning(
        "Frontend directory not found (checked %s). Running as API-only.",
        _FRONTEND_CANDIDATES,
    )
