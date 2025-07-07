import os
import pickle
import time
from typing import Any

# The synchronous Redis client
import redis  # type: ignore

try:
    # The asyncio-compatible Redis client (redis>=4.x provides redis.asyncio)
    import redis.asyncio as aioredis  # type: ignore
except ImportError:  # pragma: no cover
    aioredis = None  # Fallback if async client isn't available

from app.core.logger import get_logger

logger = get_logger(name="redis_cache")

REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "forge")


class _BaseFallbackMixin:
    """Provides an in-process fallback store for objects that cannot be pickled.

    This is mainly to keep ProviderService *instances* cached per process while
    all other serialisable entities live in Redis and are therefore shared
    across gunicorn workers.
    """

    def __init__(self):
        self._fallback_cache: dict[str, Any] = {}
        self._fallback_expiry: dict[str, float] = {}

    def _fallback_get(self, key: str) -> Any | None:
        if key not in self._fallback_cache:
            return None
        # Honour TTL semantics for fallback entries
        if time.time() > self._fallback_expiry.get(key, 0):
            # Expired – drop it
            del self._fallback_cache[key]
            del self._fallback_expiry[key]
            return None
        return self._fallback_cache[key]

    def _fallback_set(self, key: str, value: Any, ttl: int | None, default_ttl: int):
        self._fallback_cache[key] = value
        self._fallback_expiry[key] = time.time() + (ttl or default_ttl or float("inf"))

    def _fallback_delete(self, key: str):
        if key in self._fallback_cache:
            del self._fallback_cache[key]
            self._fallback_expiry.pop(key, None)

    def _fallback_clear(self):
        self._fallback_cache.clear()
        self._fallback_expiry.clear()


class RedisCache(_BaseFallbackMixin):
    """A Redis-backed cache that mimics the public API of app.core.cache.Cache.

    Objects are serialised with pickle. If an object cannot be pickled we keep
    it in a local, per-process cache so existing logic still works (but without
    cross-worker sharing for that particular key).
    """

    def __init__(self, ttl_seconds: int = 300):
        super().__init__()
        if not REDIS_URL:
            raise RuntimeError(
                "REDIS_URL environment variable must be set to use RedisCache"
            )
        self.client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    # Internal helpers -----------------------------------------------------

    @staticmethod
    def _prefixed(key: str) -> str:
        return f"{REDIS_PREFIX}:{key}"

    # Public API -----------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        # 1) check fallback store first – cheapest path
        value = self._fallback_get(key)
        if value is not None:
            self.hits += 1
            return value

        # 2) check Redis – handle connection issues gracefully (e.g. CI without Redis)
        try:
            raw = self.client.get(self._prefixed(key))
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "RedisCache: connection error during GET – falling back (%s)", exc
            )
            self.misses += 1
            return default

        if raw is None:
            self.misses += 1
            return default

        try:
            value = pickle.loads(raw)
            self.hits += 1
            return value
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "RedisCache: failed to load pickled value for %s – %s", key, exc
            )
            self.misses += 1
            return default

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl_final = ttl or self.ttl
        pickled = None
        try:
            pickled = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            # Store in fallback
            self._fallback_set(key, value, ttl, self.ttl)
            return

        try:
            self.client.set(self._prefixed(key), pickled, ex=ttl_final)
        except Exception as exc:
            logger.error("RedisCache: unable to SET key %s in Redis – %s", key, exc)
            # Fallback to local
            self._fallback_set(key, value, ttl, self.ttl)

    def delete(self, key: str) -> None:
        self._fallback_delete(key)
        try:
            self.client.delete(self._prefixed(key))
        except Exception as exc:  # pragma: no cover
            logger.error("RedisCache: unable to DELETE key %s – %s", key, exc)

    def clear(self) -> None:
        self._fallback_clear()
        # Cautious scan & delete to avoid nuking other data in shared Redis DB
        try:
            cursor = 0
            pattern = f"{REDIS_PREFIX}:*"
            while True:
                cursor, keys = self.client.scan(
                    cursor=cursor, match=pattern, count=1000
                )
                if keys:
                    self.client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:  # pragma: no cover
            logger.error("RedisCache: unable to CLEAR cache in Redis – %s", exc)

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        try:
            redis_entries = len(list(self.client.scan_iter(match=f"{REDIS_PREFIX}:*")))
        except Exception:
            redis_entries = -1
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate": hit_rate,
            "entries": redis_entries + len(self._fallback_cache),
        }


# ----------------------------------------------------------------------------
# Async variant
# ----------------------------------------------------------------------------


class AsyncRedisCache(_BaseFallbackMixin):
    """Async-compatible Redis cache matching the AsyncCache public API."""

    def __init__(self, ttl_seconds: int = 300):
        if aioredis is None:
            raise RuntimeError("redis.asyncio is required for AsyncRedisCache")
        super().__init__()
        self.client = aioredis.from_url(REDIS_URL, decode_responses=False)
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0
        # Use asyncio.Lock for compatibility with existing AsyncCache contract
        import asyncio

        self.lock = asyncio.Lock()

    @staticmethod
    def _prefixed(key: str) -> str:
        return f"{REDIS_PREFIX}:{key}"

    async def get(self, key: str, default: Any = None) -> Any:
        async with self.lock:
            # 1) fallback
            val = self._fallback_get(key)
            if val is not None:
                self.hits += 1
                return val

            # 2) check Redis – handle connection issues gracefully (e.g. CI without Redis)
            try:
                raw = await self.client.get(self._prefixed(key))
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "AsyncRedisCache: connection error during GET – falling back (%s)",
                    exc,
                )
                self.misses += 1
                return default

            if raw is None:
                self.misses += 1
                return default

            try:
                val = pickle.loads(raw)
                self.hits += 1
                return val
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "AsyncRedisCache: failed to unpickle key %s – %s", key, exc
                )
                self.misses += 1
                return default

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        async with self.lock:
            ttl_final = ttl or self.ttl
            try:
                pickled = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
            except Exception:
                self._fallback_set(key, value, ttl, self.ttl)
                return
            try:
                await self.client.set(self._prefixed(key), pickled, ex=ttl_final)
            except Exception as exc:  # pragma: no cover
                logger.error("AsyncRedisCache: unable to SET key %s – %s", key, exc)
                self._fallback_set(key, value, ttl, self.ttl)

    async def delete(self, key: str) -> None:
        async with self.lock:
            self._fallback_delete(key)
            try:
                await self.client.delete(self._prefixed(key))
            except Exception as exc:  # pragma: no cover
                logger.error("AsyncRedisCache: unable to DELETE key %s – %s", key, exc)

    async def clear(self) -> None:
        async with self.lock:
            self._fallback_clear()
            try:
                async for k in self.client.scan_iter(match=f"{REDIS_PREFIX}:*"):
                    await self.client.delete(k)
            except Exception as exc:  # pragma: no cover
                logger.error(
                    "AsyncRedisCache: unable to CLEAR cache in Redis – %s", exc
                )

    async def stats(self) -> dict[str, Any]:
        async with self.lock:
            total = self.hits + self.misses
            hit_rate = self.hits / total if total > 0 else 0.0
            try:
                entries = len(
                    [k async for k in self.client.scan_iter(match=f"{REDIS_PREFIX}:*")]
                )
            except Exception:
                entries = -1
            return {
                "hits": self.hits,
                "misses": self.misses,
                "total": total,
                "hit_rate": hit_rate,
                "entries": entries + len(self._fallback_cache),
            }
