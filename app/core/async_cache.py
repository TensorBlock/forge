"""
Async-compatible cache implementation that can be extended to work with distributed caching services.
This is a bridge toward using external caching services like AWS ElasticCache.
"""

import asyncio
import functools
import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from app.api.schemas.cached_user import CachedUser
from app.core.logger import get_logger
from app.models.forge_api_key import ForgeApiKey
from app.models.user import User

logger = get_logger(name="async_cache")

# Debug mode can be enabled via environment variable
DEBUG_CACHE = os.getenv("DEBUG_CACHE", "false").lower() == "true" or os.getenv(
    "FORGE_DEBUG_LOGGING", "false"
).lower() in ("true", "1")

if DEBUG_CACHE:
    logger.info("🐛 Cache debugging is enabled. You will see cache operations logged.")

# Add constants at the top of the file, after imports
CACHE_HIT_RATE_THRESHOLD = 0.5  # 50% threshold for cache hit rate warning
MAX_USER_CACHE_ENTRIES = 1000  # Maximum number of cached users before warning
MAX_PROVIDER_CACHE_ENTRIES = (
    100  # Maximum number of cached provider services before warning
)

T = TypeVar("T")


class AsyncCache:
    """Async-compatible cache implementation that can be extended to work with distributed cache services"""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize the cache with a default TTL"""
        # For now, we'll use a simple in-memory dict, but this can be replaced
        # with a client for external cache services like Redis or Memcached
        self.cache: dict[str, dict[str, Any]] = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0
        self.expiry = {}
        self.lock = asyncio.Lock()  # Lock for thread safety in async context

    async def get(self, key: str, default: Any = None) -> Any:
        """Get an item from the cache. If the item is not found or is expired,
        return the default value.
        """
        async with self.lock:
            if key in self.cache and (
                self.ttl is None or time.time() < self.expiry.get(key, 0)
            ):
                if DEBUG_CACHE:
                    logger.debug(f"Cache HIT for key: {key}")
                self.hits += 1
                return self.cache[key]
            if DEBUG_CACHE:
                logger.debug(f"Cache MISS for key: {key}")
            self.misses += 1
            return default

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Add an item to the cache with an optional TTL."""
        async with self.lock:
            self.cache[key] = value
            self.expiry[key] = time.time() + (ttl or self.ttl or float("inf"))
            if DEBUG_CACHE:
                logger.debug(f"Cache SET for key: {key} with TTL: {ttl or self.ttl}")

    async def delete(self, key: str) -> None:
        """Delete a value from the cache asynchronously"""
        async with self.lock:
            if key in self.cache:
                if DEBUG_CACHE:
                    logger.debug(f"Cache: Deleting key: {key[:8]}...")
                del self.cache[key]

    async def clear(self) -> None:
        """Clear all values from the cache asynchronously"""
        if DEBUG_CACHE:
            logger.debug("Cache: Clearing all entries")
        async with self.lock:
            self.cache.clear()

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics asynchronously"""
        async with self.lock:
            total = self.hits + self.misses
            hit_rate = self.hits / total if total > 0 else 0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "total": total,
                "hit_rate": hit_rate,
                "entries": len(self.cache),
            }


def async_cached(cache_instance: AsyncCache, key_func: Callable[[Any], str] = None):
    """Decorator to cache async function results"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default: use the first argument (often 'self') and function name
                key = f"{func.__name__}:{id(args[0])}"

            result = await cache_instance.get(key)
            if result is None:
                result = await func(*args, **kwargs)
                if result is not None:  # Don't cache None results
                    await cache_instance.set(key, result)
            return result

        return wrapper

    return decorator


# Decide cache backend (shared Redis vs in-memory) for async context
if os.getenv("FORCE_MEMORY_CACHE", "false").lower() == "true":
    _AsyncBackend = AsyncCache
    if DEBUG_CACHE:
        logger.info(
            "Async cache backend: In-memory Cache (forced by FORCE_MEMORY_CACHE)"
        )
elif os.getenv("REDIS_URL"):
    try:
        from app.core.redis_cache import AsyncRedisCache as _AsyncBackend

        if DEBUG_CACHE:
            logger.info("Async cache backend: AsyncRedisCache (shared across workers)")
    except Exception as exc:
        logger.warning(
            "Could not initialise AsyncRedisCache (%s). Falling back to in-memory async cache.",
            exc,
        )
        _AsyncBackend = AsyncCache
else:
    _AsyncBackend = AsyncCache

async_user_cache: "AsyncCache" = _AsyncBackend(ttl_seconds=300)  # 5-min TTL
async_provider_service_cache: "AsyncCache" = _AsyncBackend(
    ttl_seconds=3600
)  # 1-hour TTL


# User-specific functions
async def get_cached_user_async(api_key: str) -> CachedUser | None:
    """Get a user from cache by API key asynchronously"""
    if not api_key:
        return None
    cached_data = await async_user_cache.get(f"user:{api_key}")
    if cached_data:
        return CachedUser.model_validate(cached_data)
    return None


async def cache_user_async(api_key: str, user: User) -> None:
    """Cache a user by API key asynchronously"""
    if not api_key or user is None:
        return
    cached_user = CachedUser.model_validate(user)
    await async_user_cache.set(f"user:{api_key}", cached_user.model_dump())


async def invalidate_user_cache_async(api_key: str) -> None:
    """Invalidate user cache for a specific API key asynchronously"""
    if not api_key:
        return
    await async_user_cache.delete(f"user:{api_key}")


async def invalidate_forge_scope_cache_async(api_key: str) -> None:
    """Invalidate forge scope cache for a specific API key asynchronously"""
    if not api_key:
        return
    
    # The cache key format uses the API key WITHOUT the "forge-" prefix
    # to match how it's set in get_user_by_api_key()
    cache_key = api_key
    if cache_key.startswith("forge-"):
        cache_key = cache_key[6:]  # Remove "forge-" prefix to match cache setting format
    
    await async_provider_service_cache.delete(f"forge_scope:{cache_key}")
    
    if DEBUG_CACHE:
        # Mask the API key for logging
        masked_key = cache_key[:8] + "..." if len(cache_key) > 8 else cache_key
        logger.debug(f"Cache: Invalidated forge scope cache for API key: {masked_key} (async)")


async def invalidate_user_cache_by_id_async(user_id: int) -> None:
    """Invalidate all cache entries for a specific user ID asynchronously"""
    if not user_id:
        return

    keys_to_invalidate = []

    # Case 1: in-memory backend exposes .cache dict
    if hasattr(async_user_cache, "cache"):
        async with async_user_cache.lock:
            for key in list(async_user_cache.cache.keys()):
                if key.startswith("user:"):
                    user_data = await async_user_cache.get(key)
                    if user_data and user_data.get("id") == user_id:
                        keys_to_invalidate.append(key)

    # Case 2: Redis backend
    if hasattr(async_user_cache, "client"):
        try:
            pattern = f"{os.getenv('REDIS_PREFIX', 'forge')}:user:*"
            async for redis_key in async_user_cache.client.scan_iter(match=pattern):
                key_str = (
                    redis_key.decode() if isinstance(redis_key, bytes) else redis_key
                )
                key_without_prefix = key_str.split(":", 1)[-1]
                user_data = await async_user_cache.get(key_without_prefix)
                if user_data and user_data.get("id") == user_id:
                    keys_to_invalidate.append(key_without_prefix)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Failed to scan Redis keys during async user cache invalidation – %s",
                exc,
            )

    # Invalidate each key
    for key in keys_to_invalidate:
        await async_user_cache.delete(key)
        if DEBUG_CACHE:
            logger.debug(f"Cache: Invalidated user cache for key: {key[:8]}...")


# Provider service functions
async def get_cached_provider_service_async(user_id: int) -> Any:
    """Get a provider service from cache by user ID asynchronously"""
    if not user_id:
        return None
    return await async_provider_service_cache.get(f"provider_service:{user_id}")


async def cache_provider_service_async(user_id: int, service: Any) -> None:
    """Cache a provider service by user ID asynchronously"""
    if not user_id or service is None:
        return
    await async_provider_service_cache.set(f"provider_service:{user_id}", service)


async def invalidate_provider_service_cache_async(user_id: int) -> None:
    """Invalidate provider service cache for a specific user ID asynchronously"""
    if not user_id:
        return

    # Delete the provider service instance from cache
    await async_provider_service_cache.delete(f"provider_service:{user_id}")

    # Delete provider keys from cache
    await async_provider_service_cache.delete(f"provider_keys:{user_id}")

    # No per-process model caches to clear now – shared cache handled separately.

    if DEBUG_CACHE:
        logger.debug(
            f"Cache: Cleared provider service, keys, and models caches for user {user_id} (async)"
        )


async def invalidate_provider_models_cache_async(provider_name: str) -> None:
    """Invalidate model cache for a specific provider asynchronously"""
    if not provider_name:
        return

    prefix = f"models:{provider_name}:"

    # Case 1: in-memory backend
    if hasattr(async_provider_service_cache, "cache"):
        async with async_provider_service_cache.lock:
            for key in list(async_provider_service_cache.cache.keys()):
                if key.startswith(prefix):
                    await async_provider_service_cache.delete(key)

    # Case 2: Redis backend
    if hasattr(async_provider_service_cache, "client"):
        try:
            redis_prefix = f"{os.getenv('REDIS_PREFIX', 'forge')}:{prefix}*"
            async for redis_key in async_provider_service_cache.client.scan_iter(
                match=redis_prefix
            ):
                key_str = (
                    redis_key.decode() if isinstance(redis_key, bytes) else redis_key
                )
                internal_key = key_str.split(":", 1)[-1]
                await async_provider_service_cache.delete(internal_key)
        except Exception as exc:
            logger.warning(
                "Failed to scan Redis keys during async model cache invalidation – %s",
                exc,
            )

    # Clear L1 cache in ProviderService (per-process)
    from app.services.provider_service import ProviderService

    ProviderService._models_l1_cache = {
        k: v
        for k, v in ProviderService._models_l1_cache.items()
        if not k.startswith(prefix)
    }

    if DEBUG_CACHE:
        logger.debug(
            f"Cache: Invalidated model cache for provider: {provider_name} (async)"
        )


async def invalidate_all_caches_async() -> None:
    """Invalidate all caches in the system asynchronously"""
    await async_user_cache.clear()
    await async_provider_service_cache.clear()

    if DEBUG_CACHE:
        logger.debug("Cache: Invalidated all caches")


async def warm_cache_async(db: Session) -> None:
    """Pre-cache frequently accessed data asynchronously"""
    from app.models.user import User
    from app.services.provider_service import ProviderService

    if DEBUG_CACHE:
        logger.info("Cache: Starting cache warm-up...")

    # Cache active users
    active_users = db.query(User).filter(User.is_active).all()
    for user in active_users:
        # Get user's Forge API keys
        forge_api_keys = (
            db.query(ForgeApiKey)
            .filter(ForgeApiKey.user_id == user.id, ForgeApiKey.is_active)
            .all()
        )
        for key in forge_api_keys:
            # Cache user with their Forge API key
            await cache_user_async(key.key, user)

    # Cache provider services for active users
    for user in active_users:
        service = await ProviderService.async_get_instance(user, db)
        await cache_provider_service_async(user.id, service)

    if DEBUG_CACHE:
        logger.info(f"Cache: Warm-up complete. Cached {len(active_users)} users")


async def get_cache_stats_async() -> dict[str, dict[str, Any]]:
    """Get comprehensive cache statistics asynchronously"""
    return {
        "user_cache": await async_user_cache.stats(),
        "provider_service_cache": await async_provider_service_cache.stats(),
    }


async def monitor_cache_performance_async() -> dict[str, Any]:
    """Monitor cache performance and return metrics asynchronously"""
    stats = await get_cache_stats_async()

    # Calculate overall hit rates
    total_hits = stats["user_cache"]["hits"] + stats["provider_service_cache"]["hits"]
    total_requests = (
        stats["user_cache"]["total"] + stats["provider_service_cache"]["total"]
    )
    overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0.0

    # Check for potential issues
    issues = []
    if overall_hit_rate < CACHE_HIT_RATE_THRESHOLD:  # Less than threshold hit rate
        issues.append("Low cache hit rate")
    if (
        stats["user_cache"]["entries"] > MAX_USER_CACHE_ENTRIES
    ):  # More than max cached users
        issues.append("Large user cache size")
    if (
        stats["provider_service_cache"]["entries"] > MAX_PROVIDER_CACHE_ENTRIES
    ):  # More than max cached services
        issues.append("Large provider service cache size")

    return {"stats": stats, "overall_hit_rate": overall_hit_rate, "issues": issues}
