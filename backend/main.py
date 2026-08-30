"""
main.py — FastAPI application entry point for GroceryAI.

Endpoints
---------
POST /api/compare        — compare prices across all apps for a grocery list
POST /api/analyze-images — identify products from images, then compare prices
GET  /api/health         — simple health check
GET  /api/apps           — list of supported apps
GET  /                   — serves frontend/index.html (fallback when nginx is
                           not the public entry point, e.g. Render free tier)
"""

import logging
import sys
import os

# Allow imports relative to /backend (for running outside Docker too)
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import SUPPORTED_APPS, CORS_ORIGINS, MAX_IMAGE_SIZE_BYTES, MAX_IMAGES
from models.schemas import (
    CompareRequest, CompareResponse,
    ImageAnalyzeRequest, ImageAnalyzeResponse, DetectedProductSchema,
)
from ai.normalizer import normalize
from ai.vision_service import identify_products, VisionStatus
from services import aggregator, ranker as ranker_svc
from cache import redis_cache

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static frontend directory
# In the prod Docker image the frontend is copied to /usr/share/nginx/html.
# When running locally (outside Docker) we fall back to ../frontend relative
# to this file.  If neither path exists, static serving is silently skipped
# and the app works as an API-only server.
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FRONTEND_CANDIDATES = [
    "/usr/share/nginx/html",           # prod Docker image
    os.path.join(_THIS_DIR, "..", "frontend"),  # local / dev
]
FRONTEND_DIR: str | None = next(
    (p for p in _FRONTEND_CANDIDATES if os.path.isfile(os.path.join(p, "index.html"))),
    None,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="GroceryAI",
    description="Compare grocery prices across Blinkit, Zepto, Instamart and Flipkart Minutes.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["meta"])
async def health():
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/apps", tags=["meta"])
async def list_apps():
    """Return the list of supported grocery apps."""
    return {"apps": SUPPORTED_APPS}


@app.post("/api/compare", response_model=CompareResponse, tags=["compare"])
async def compare_prices(body: CompareRequest):
    """
    Compare grocery prices across all supported apps.

    Body
    ----
    ```json
    {
      "items": ["Amul Milk 1L", "Maggi 70g x5"],
      "pincode": "560001"
    }
    ```

    Returns a ranked list (cheapest first) with per-item breakdowns.
    """
    if not body.items:
        raise HTTPException(status_code=422, detail="items list must not be empty")

    # --- 1. Check cache ---
    cache_key = redis_cache.make_key("compare", body.items, body.pincode)
    cached = await redis_cache.get_cached(cache_key)
    if cached:
        logger.info("Cache hit for key %s", cache_key)
        return CompareResponse(**cached)

    # --- 2. Normalise items ---
    normalised = [normalize(item) for item in body.items]
    logger.info("Normalised %d items for pincode %s", len(normalised), body.pincode)

    # --- 3. Aggregate prices from all scrapers in parallel ---
    app_prices = await aggregator.aggregate_all(normalised, body.pincode)

    if not app_prices:
        raise HTTPException(
            status_code=503,
            detail="All scrapers failed. Please try again later.",
        )

    # --- 4. Rank results ---
    ranked = ranker_svc.rank(app_prices)
    tip = ranker_svc.savings_tip(ranked)

    response = CompareResponse(
        results=ranked,
        savings_tip=tip,
        query_items=normalised,
    )

    # --- 5. Cache the response ---
    await redis_cache.set_cached(cache_key, response.model_dump())

    return response


@app.post("/api/analyze-images", response_model=ImageAnalyzeResponse, tags=["images"])
async def analyze_images(body: ImageAnalyzeRequest):
    """
    Identify grocery products from uploaded images, then compare prices.

    Body
    ----
    ```json
    {
      "images_b64": ["<base64 string>", ...],
      "pincode": "560001"
    }
    ```

    Each base64 string is a JPEG/PNG/WEBP image pre-resized client-side to ≤ 1024px.
    Returns detected products and, if any are found, a full price comparison.

    NOTE: Requires OPENAI_API_KEY environment variable to be set.
    See backend/ai/vision_service.py for setup instructions.
    """
    # --- Validate image sizes server-side ---
    for i, b64 in enumerate(body.images_b64):
        try:
            import base64 as _b64
            decoded_size = len(_b64.b64decode(b64, validate=True))
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=f"Image {i + 1} is not valid base64 data.",
            )
        if decoded_size > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Image {i + 1} is too large ({decoded_size // 1024} KB). "
                    f"Maximum allowed is {MAX_IMAGE_SIZE_BYTES // 1024} KB per image."
                ),
            )

    logger.info("Analyzing %d images for pincode %s", len(body.images_b64), body.pincode)

    # --- 1. Run vision service ---
    vision_result = await identify_products(body.images_b64)

    # All non-OK statuses: return early with the user-friendly message.
    # These include: NOT_CONFIGURED, QUOTA_EXHAUSTED, RATE_LIMITED, AUTH_ERROR,
    # ERROR, NO_PRODUCTS — none of which should expose raw internal details.
    if vision_result.status != VisionStatus.OK:
        logger.info(
            "Vision service returned non-OK status '%s' for %d image(s): %s",
            vision_result.status,
            len(body.images_b64),
            vision_result.error_message[:120],
        )
        return ImageAnalyzeResponse(
            vision_status=vision_result.status.value,
            error_message=vision_result.error_message or "Image analysis could not be completed.",
        )

    # --- 2. Convert detected products to schema ---
    detected = [
        DetectedProductSchema(
            name=p.name,
            confidence=p.confidence,
            from_image_index=p.from_image_index,
        )
        for p in vision_result.products
    ]
    product_names = [p.name for p in vision_result.products]

    logger.info("Vision identified %d products: %s", len(product_names), product_names[:5])

    # --- 3. Run price comparison for identified products ---
    try:
        cache_key = redis_cache.make_key("compare", product_names, body.pincode)
        cached = await redis_cache.get_cached(cache_key)
        if cached:
            compare_response = CompareResponse(**cached)
        else:
            normalised = [normalize(name) for name in product_names]
            app_prices = await aggregator.aggregate_all(normalised, body.pincode)
            if app_prices:
                ranked = ranker_svc.rank(app_prices)
                tip = ranker_svc.savings_tip(ranked)
                compare_response = CompareResponse(
                    results=ranked,
                    savings_tip=tip,
                    query_items=normalised,
                )
                await redis_cache.set_cached(cache_key, compare_response.model_dump())
            else:
                compare_response = None
    except Exception as exc:
        logger.exception("Price comparison failed after vision: %s", exc)
        compare_response = None

    return ImageAnalyzeResponse(
        vision_status=VisionStatus.OK.value,
        detected=detected,
        compare_result=compare_response,
    )


# ---------------------------------------------------------------------------
# Frontend static files — mounted AFTER all /api/* routes so API routes win.
#
# This makes uvicorn itself serve the frontend when nginx is not the public
# entry point (e.g. when Render runs the container without BUILD_TARGET=prod
# or when the service was created manually via the Render dashboard UI).
#
# Route priority (FastAPI processes routes top-to-bottom):
#   /api/*   → handled by the endpoint functions above
#   /        → FileResponse(index.html)
#   /app.js, /style.css, /favicon.svg, etc. → StaticFiles
# ---------------------------------------------------------------------------
if FRONTEND_DIR:
    logger.info("Serving frontend from: %s", FRONTEND_DIR)

    @app.get("/", include_in_schema=False)
    async def serve_index():
        """Serve the GroceryAI SPA root page."""
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    # Mount all other static assets (JS, CSS, images, manifest, etc.)
    # The mount must come last — it acts as a catch-all for unmatched paths.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    logger.warning(
        "Frontend directory not found (checked %s). "
        "Running as API-only — set FRONTEND_DIR env var if needed.",
        _FRONTEND_CANDIDATES,
    )
