"""
Thin caching layer on top of Django's cache framework (Redis).
Provides per-data-type TTLs so that hot paths (rider locations)
refresh frequently while heavier aggregates live longer.
"""
import functools
import hashlib
import json
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── TTLs (seconds) ───────────────────────────────────────────────────────────

CACHE_TTL = {
    "rider_locations":  30,      # map view — near real-time
    "rider_performance": 120,    # 2 minutes
    "merchant_analytics": 120,   # 2 minutes
    "zone_dashboard":   300,     # 5 minutes
    "verticals":        300,     # 5 minutes
    "vertical_detail":  300,
    "zone_riders":      120,
    "zone_merchants":   120,
    "leaderboard":      300,     # 5 minutes
    "order_analytics":  300,
}


def _make_key(prefix: str, *parts) -> str:
    """Build a deterministic cache key from prefix + variable parts."""
    raw = f"{prefix}:" + ":".join(str(p) for p in parts if p is not None)
    # Keep keys short — hash long param combos
    if len(raw) > 200:
        raw = f"{prefix}:{hashlib.md5(raw.encode()).hexdigest()}"
    return raw


def cached_axpress_call(data_type: str):
    """
    Decorator that caches the return value of an axpress_client function.

    Usage::

        @cached_axpress_call("verticals")
        def get_verticals(period="this_month"):
            return axpress_client.get_verticals(period)

    The cache key is built from the function name + all positional/keyword args.
    """
    ttl = CACHE_TTL.get(data_type, 300)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = _make_key(f"occ:{data_type}", fn.__name__, *args, *sorted(kwargs.items()))
            result = cache.get(key)
            if result is not None:
                return result
            result = fn(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator


def invalidate(data_type: str, *key_parts):
    """Manually bust a specific cache entry."""
    key = _make_key(f"occ:{data_type}", *key_parts)
    cache.delete(key)


def invalidate_pattern(pattern: str):
    """
    Delete all cache keys matching a pattern (Redis-only).
    Falls back to no-op if the cache backend doesn't support key scanning.
    """
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        keys = conn.keys(f"*{pattern}*")
        if keys:
            conn.delete(*keys)
            logger.info("Invalidated %d cache keys matching '%s'", len(keys), pattern)
    except Exception:
        logger.debug("Cache pattern invalidation not supported or failed for '%s'", pattern)
