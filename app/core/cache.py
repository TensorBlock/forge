import functools
import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from app.api.schemas.cached_user import CachedUser
from app.core.logger import get_logger
from app.models.user import User

logger = get_logger(name="cache")

T = TypeVar("T")

# Debug mode can be enabled via environment variable
DEBUG_CACHE = os.getenv("DEBUG_CACHE", "false").lower() == "true" or os.getenv(
    "FORGE_DEBUG_LOGGING", "false"
).lower() in ("true", "1")

# Print cache status at initialization
if DEBUG_CACHE:
    logger.info("🐛 Cache debugging is enabled. You will see cache operations logged.")

# Add constants at the top of the file, after imports
CACHE_HIT_RATE_THRESHOLD = 0.5  # 50% threshold for cache hit rate warning
MAX_USER_CACHE_ENTRIES = 1000  # Maximum number of cached users before warning
MAX_PROVIDER_CACHE_ENTRIES = (
    100  # Maximum number of cached provider services before warning
)


class Cache:
    """Simple in-memory cache implementation with logging support."""

    def __init__(self, ttl_seconds: int = 300):
        self.cache: dict[str, dict[str, Any]] = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0
        self.expiry = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item from the cache. If the item is not found or is expired,
        return the default value.
        """
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

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Add an item to the cache with an optional TTL."""
        self.cache[key] = value
        self.expiry[key] = time.time() + (ttl or self.ttl or float("inf"))
        if DEBUG_CACHE:
            logger.debug(f"Cache SET for key: {key} with TTL: {ttl or self.ttl}")

    def delete(self, key: str) -> None:
        """Delete a value from the cache"""
        if key in self.cache:
            if DEBUG_CACHE:
                logger.debug(f"Cache: Deleting key: {key[:8]}...")
            del self.cache[key]

    def clear(self) -> None:
        """Clear all values from the cache"""
        if DEBUG_CACHE:
            logger.debug("Cache: Clearing all entries")
        self.cache.clear()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate": hit_rate,
            "entries": len(self.cache),
        }


# Decide which backend to use. If a Redis URL is configured we switch to the
# shared Redis-based cache; otherwise we fall back to the in-process Cache so
# that the application continues to work in local development / unit tests.

# Force in-memory cache for testing environments
if os.getenv("FORCE_MEMORY_CACHE", "false").lower() == "true":
    _CacheBackend = Cache
    if DEBUG_CACHE:
        logger.info("Cache backend: In-memory Cache (forced by FORCE_MEMORY_CACHE)")
elif os.getenv("REDIS_URL"):
    try:
        from app.core.redis_cache import RedisCache as _CacheBackend

        if DEBUG_CACHE:
            logger.info("Cache backend: RedisCache (shared across workers)")
    except Exception as exc:
        # Fail gracefully to in-memory cache if Redis is unavailable at import
        logger.warning(
            "Could not initialise RedisCache (%s). Falling back to in-memory cache.",
            exc,
        )
        _CacheBackend = Cache
else:
    _CacheBackend = Cache

# Expose the global cache instances
user_cache: "Cache" = _CacheBackend(ttl_seconds=300)  # 5-minute TTL for users
provider_service_cache: "Cache" = _CacheBackend(ttl_seconds=3600)  # 1-hour TTL


def cached(cache_instance: Cache, key_func: Callable[[Any], str] = None):
    """Decorator to cache function results"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default: use the first argument (often 'self') and function name
                key = f"{func.__name__}:{id(args[0])}"

            result = cache_instance.get(key)
            if result is None:
                result = func(*args, **kwargs)
                if result is not None:  # Don't cache None results
                    cache_instance.set(key, result)
            return result

        return wrapper

    return decorator


# User-specific functions
def get_cached_user(api_key: str) -> CachedUser | None:
    """Get a user from cache by API key"""
    if not api_key:
        return None
    cached_data = user_cache.get(f"user:{api_key}")
    if cached_data:
        return CachedUser.model_validate(cached_data)
    return None


def cache_user(api_key: str, user: User) -> None:
    """Cache a user by API key"""
    if not api_key or user is None:
        return
    cached_user = CachedUser.model_validate(user)
    user_cache.set(f"user:{api_key}", cached_user.model_dump())


def invalidate_user_cache(api_key: str) -> None:
    """Invalidate user cache for a specific API key"""
    if not api_key:
        return
    user_cache.delete(f"user:{api_key}")


def invalidate_forge_scope_cache(api_key: str) -> None:
    """Invalidate forge scope cache for a specific API key.
    
    Args:
        api_key (str): The API key to invalidate cache for. Can include or exclude 'forge-' prefix.
    """
    if not api_key:
        return
    
    # The cache key format uses the API key WITHOUT the "forge-" prefix
    # to match how it's set in get_user_by_api_key()
    cache_key = api_key
    if cache_key.startswith("forge-"):
        cache_key = cache_key[6:]  # Remove "forge-" prefix to match cache setting format
    
    provider_service_cache.delete(f"forge_scope:{cache_key}")
    
    if DEBUG_CACHE:
        # Mask the API key for logging
        masked_key = cache_key[:8] + "..." if len(cache_key) > 8 else cache_key
        logger.debug(f"Cache: Invalidated forge scope cache for API key: {masked_key}")


# Provider service functions
def get_cached_provider_service(user_id: int) -> Any:
    """Get a provider service from cache by user ID"""
    if not user_id:
        return None
    return provider_service_cache.get(f"provider_service:{user_id}")


def cache_provider_service(user_id: int, service: Any) -> None:
    """Cache a provider service by user ID"""
    if not user_id or service is None:
        return
    provider_service_cache.set(f"provider_service:{user_id}", service)


def invalidate_provider_service_cache(user_id: int) -> None:
    """Invalidate provider service cache for a specific user ID"""
    if not user_id:
        return

    # Delete the provider service instance from cache
    provider_service_cache.delete(f"provider_service:{user_id}")

    # Delete provider keys from cache
    provider_service_cache.delete(f"provider_keys:{user_id}")

    # Also clear shared model cache keys for this user (provider-specific cache
    # entries are independent, but we remove any potential per-process fallbacks)

    if DEBUG_CACHE:
        logger.debug(
            f"Cache: Cleared provider service, keys, and models caches for user {user_id}"
        )


def invalidate_user_cache_by_id(user_id: int) -> None:
    """Invalidate all cache entries for a specific user ID"""
    if not user_id:
        return

    keys_to_invalidate = []

    # Case 1: in-memory backend exposes the internal dict
    if hasattr(user_cache, "cache"):
        for key in list(user_cache.cache.keys()):
            if key.startswith("user:"):
                user_data = user_cache.get(key)
                if user_data and user_data.id == user_id:
                    keys_to_invalidate.append(key)

    # Case 2: Redis backend – iterate through keys in Redis
    if hasattr(user_cache, "client"):
        try:
            pattern = f"{os.getenv('REDIS_PREFIX', 'forge')}:user:*"
            for redis_key in user_cache.client.scan_iter(match=pattern):
                # Strip prefix before checking
                key_str = (
                    redis_key.decode() if isinstance(redis_key, bytes) else redis_key
                )
                # Remove prefix and colon
                key_without_prefix = key_str.split(":", 1)[-1]
                user_data = user_cache.get(key_without_prefix)
                if user_data and user_data.id == user_id:
                    keys_to_invalidate.append(key_without_prefix)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Failed to scan Redis keys during user cache invalidation – %s", exc
            )

    # Invalidate each key
    for key in keys_to_invalidate:
        user_cache.delete(key)
        if DEBUG_CACHE:
            logger.debug(f"Cache: Invalidated user cache for key: {key[:8]}...")


def invalidate_provider_models_cache(provider_name: str) -> None:
    """Invalidate model cache for a specific provider"""
    if not provider_name:
        return

    # Build prefix used for shared cache keys
    prefix = f"models:{provider_name}:"

    # Case 1: in-memory backend exposes underlying dict
    if hasattr(provider_service_cache, "cache"):
        for key in list(provider_service_cache.cache.keys()):
            if key.startswith(prefix):
                provider_service_cache.delete(key)

    # Case 2: Redis backend exposes .client
    if hasattr(provider_service_cache, "client"):
        try:
            redis_prefix = f"{os.getenv('REDIS_PREFIX', 'forge')}:{prefix}*"
            for redis_key in provider_service_cache.client.scan_iter(
                match=redis_prefix
            ):
                key_str = (
                    redis_key.decode() if isinstance(redis_key, bytes) else redis_key
                )
                # remove the global prefix so .delete will add it back
                internal_key = key_str.split(":", 1)[-1]
                provider_service_cache.delete(internal_key)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Failed to scan Redis keys during model cache invalidation – %s", exc
            )

    # Clear L1 cache entries in ProviderService
    from app.services.provider_service import ProviderService

    # Clear all L1 cache entries for this provider
    ProviderService._models_l1_cache.clear()

    if DEBUG_CACHE:
        logger.debug(f"Cache: Invalidated model cache for provider: {provider_name}")


def invalidate_all_caches() -> None:
    """Invalidate all caches in the system"""
    user_cache.clear()
    provider_service_cache.clear()

    if DEBUG_CACHE:
        logger.debug("Cache: Invalidated all caches")


async def warm_cache(db: Session) -> None:
    """Pre-cache frequently accessed data"""
    from app.core.security import decrypt_api_key
    from app.models.provider_key import ProviderKey
    from app.models.user import User
    from app.services.provider_service import ProviderService

    if DEBUG_CACHE:
        logger.info("Cache: Starting cache warm-up...")

    # Cache active users
    active_users = db.query(User).filter(User.is_active).all()
    for user in active_users:
        # Get user's API keys
        api_keys = db.query(ProviderKey).filter(ProviderKey.user_id == user.id).all()
        for key in api_keys:
            # Decrypt the API key before caching
            decrypted_key = decrypt_api_key(key.encrypted_api_key)
            cache_user(decrypted_key, user)

    # Cache provider services for active users
    for user in active_users:
        service = ProviderService.get_instance(user, db)
        cache_provider_service(user.id, service)

    if DEBUG_CACHE:
        logger.info(f"Cache: Warm-up complete. Cached {len(active_users)} users")


def get_cache_stats() -> dict[str, dict[str, Any]]:
    """Get comprehensive cache statistics"""
    return {
        "user_cache": user_cache.stats(),
        "provider_service_cache": provider_service_cache.stats(),
    }


def monitor_cache_performance() -> dict[str, Any]:
    """Monitor cache performance and return metrics"""
    stats = get_cache_stats()

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
