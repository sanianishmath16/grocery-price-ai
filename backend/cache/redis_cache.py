"""
redis_cache.py — Redis caching layer with graceful fallback.

If Redis is unavailable (e.g. running locally without Docker), all cache
operations become no-ops so the rest of the application continues working.

Usage
-----
    from cache.redis_cache import get_cached, set_cached, make_key

    key = make_key("compare", items, pincode)
    cached = await get_cached(key)
    if cached is None:
        data = await compute_something()
        await set_cached(key, data)
"""

import hashlib
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try to import redis; fall back gracefully if not installed
try:
    import redis.asyncio as aioredis  # type: ignore
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    logger.warning("redis package not installed; caching disabled.")

from config import REDIS_URL, CACHE_TTL

# Module-level async client (lazily initialised)
_client: Optional[Any] = None


async def _get_client() -> Optional[Any]:
    """Return a connected Redis client, or None if unavailable."""
    global _client
    if not _REDIS_AVAILABLE:
        return None
    if _client is None:
        try:
            _client = aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            # Ping to verify connection
            await _client.ping()
            logger.info("Redis connected at %s", REDIS_URL)
        except Exception as exc:
            logger.warning("Redis unavailable (%s); caching disabled.", exc)
            _client = None
    return _client


def make_key(prefix: str, items: list, pincode: str) -> str:
    """
    Build a deterministic cache key from a list of item strings + pincode.
    Uses an MD5 digest so keys are short and safe for Redis.
    """
    payload = json.dumps({"items": sorted(i.lower() for i in items), "pincode": pincode})
    digest = hashlib.md5(payload.encode()).hexdigest()
    return f"{prefix}:{digest}"


async def get_cached(key: str) -> Optional[Any]:
    """
    Retrieve a cached value by key.
    Returns the deserialised Python object, or None on miss / error.
    """
    client = await _get_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Cache GET error for key '%s': %s", key, exc)
        return None


async def set_cached(key: str, value: Any, ttl: int = CACHE_TTL) -> None:
    """
    Store a value in the cache with TTL seconds expiry.
    Silently ignores errors.
    """
    client = await _get_client()
    if client is None:
        return
    try:
        await client.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.warning("Cache SET error for key '%s': %s", key, exc)


async def invalidate(key: str) -> None:
    """Delete a specific cache key."""
    client = await _get_client()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception as exc:
        logger.warning("Cache DEL error for key '%s': %s", key, exc)
