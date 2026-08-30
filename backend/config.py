"""
config.py — Application-wide settings for GroceryAI.

All environment-specific values are read from environment variables so the
same Docker image works locally, on Render, Fly.io, Railway, or any VPS
without rebuilding.

Required env vars for production
---------------------------------
REDIS_URL        Redis connection string (default: redis://redis:6379/0)
OPENAI_API_KEY   OpenAI API key for image recognition (optional — feature
                 degrades gracefully when not set)

Optional env vars
-----------------
CORS_ORIGINS     Comma-separated list of allowed origins, e.g.:
                   https://groceryai.onrender.com,https://groceryai.fly.dev
                 Defaults to "*" (allow all), which is fine for a public
                 read-only API but should be tightened in production.
"""

import os
from typing import List

# ---------------------------------------------------------------------------
# Supported apps
# ---------------------------------------------------------------------------
SUPPORTED_APPS: List[str] = ["blinkit", "zepto", "instamart", "flipkart"]

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Cache TTL in seconds (15 minutes)
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "900"))

# ---------------------------------------------------------------------------
# Scraper settings
# ---------------------------------------------------------------------------
SCRAPER_TIMEOUT: float = float(os.getenv("SCRAPER_TIMEOUT", "10.0"))
SCRAPER_MAX_RETRIES: int = int(os.getenv("SCRAPER_MAX_RETRIES", "2"))
SCRAPER_RETRY_DELAY: float = float(os.getenv("SCRAPER_RETRY_DELAY", "0.5"))

# ---------------------------------------------------------------------------
# Delivery fee thresholds (per app, in INR)
# ---------------------------------------------------------------------------
DELIVERY_CONFIG = {
    "blinkit":   {"free_above": 199, "fee": 25},
    "zepto":     {"free_above": 149, "fee": 20},
    "instamart": {"free_above": 299, "fee": 30},
    "flipkart":  {"free_above": 250, "fee": 35},
}

# ---------------------------------------------------------------------------
# App-specific pricing biases
# ---------------------------------------------------------------------------
APP_PRICE_BIAS = {
    "blinkit":   {"dairy": 1.02, "snacks": 0.96, "staples": 1.00, "default": 0.99},
    "zepto":     {"dairy": 0.97, "snacks": 1.01, "staples": 0.98, "default": 0.98},
    "instamart": {"dairy": 1.00, "snacks": 0.99, "staples": 1.03, "default": 1.01},
    "flipkart":  {"dairy": 1.03, "snacks": 1.02, "staples": 0.97, "default": 1.00},
}

# ---------------------------------------------------------------------------
# Image upload settings
# ---------------------------------------------------------------------------
MAX_IMAGES: int = 10
MAX_IMAGE_SIZE_BYTES: int = 2 * 1024 * 1024  # 2 MB per image
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
_cors_env = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS: List[str] = (
    ["*"] if _cors_env.strip() == "*"
    else [o.strip() for o in _cors_env.split(",") if o.strip()]
)
