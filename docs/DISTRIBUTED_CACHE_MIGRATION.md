# Distributed Cache Migration Plan

This document outlines the strategy for migrating Forge's in-memory caching to a distributed caching solution.

## Current Limitations

The current in-memory cache implementation has several limitations:

1. **No cross-instance sharing**: Each server instance has its own isolated cache, leading to redundant API calls across servers
2. **Limited capacity**: In-memory caches are constrained by the server's RAM
3. **No persistence**: Cache is lost on server restart
4. **Inconsistency across instances**: Different servers might have different cached data

## Migration Strategy

Our approach to migrating to a distributed cache follows a phased rollout:

### Phase 1: Async-Compatible Cache Implementation (Completed)

- ✅ Created `AsyncCache` class in `app/core/async_cache.py`
- ✅ Added async-compatible cache methods
- ✅ Added `async_get_instance` method to `ProviderService`
- ✅ Created test scripts to verify functionality

### Phase 2: External Cache Client Integration

1. Integrate with an external caching service:
   - AWS ElasticCache (preferred for AWS deployments)
   - Redis (best general-purpose option)
   - Memcached (simpler option with fewer features)

2. Create provider-specific cache implementations:
   - `RedisAsyncCache` implementation using `aioredis`
   - `MemcachedAsyncCache` implementation using `aiomcache`

3. Update configuration to support external cache settings:
   ```python
   CACHE_TYPE = os.getenv("CACHE_TYPE", "memory")  # memory, redis, memcached
   CACHE_URL = os.getenv("CACHE_URL", "localhost:6379")
   CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
   ```

4. Create a cache factory to return the appropriate cache implementation:
   ```python
   def get_cache_instance(name, ttl=None):
       if CACHE_TYPE == "redis":
           return RedisAsyncCache(name, ttl or CACHE_TTL)
       elif CACHE_TYPE == "memcached":
           return MemcachedAsyncCache(name, ttl or CACHE_TTL)
       else:
           return AsyncCache(ttl or CACHE_TTL)
   ```

### Phase 3: Gradual Replacement of Sync Cache

1. Replace synchronous cache usage with async versions:
   - Update API routes to use async cache methods
   - Incrementally move from sync to async patterns

2. Implement dual-write strategy during transition:
   - Write to both in-memory and distributed cache
   - Read from distributed cache with fallback to in-memory

3. Add monitoring and metrics for cache performance:
   - Cache hit/miss rates
   - Latency metrics
   - Error rates

### Phase 4: Full Migration

1. Remove all references to sync cache implementations
2. Optimize cache usage based on monitoring data
3. Add cache warm-up procedures
4. Implement cache invalidation patterns

## External Cache Service Options

### AWS ElasticCache (Redis)

**Pros:**
- Fully managed AWS service
- Scales automatically
- Integrated with AWS monitoring
- High availability options

**Implementation:**
```bash
pip install aioredis redis
```

**Code Sample:**
```python
import aioredis

class RedisAsyncCache(AsyncCache):
    async def initialize(self, url):
        self.redis = await aioredis.create_redis_pool(url)

    async def get(self, key):
        value = await self.redis.get(key)
        if value:
            return pickle.loads(value)
        return None

    async def set(self, key, value, ttl=None):
        ttl_value = ttl or self.ttl
        await self.redis.setex(key, ttl_value, pickle.dumps(value))
```

### Memcached

**Pros:**
- Simpler setup
- Lower memory overhead
- Wide adoption

**Implementation:**
```bash
pip install aiomcache
```

**Code Sample:**
```python
import aiomcache
import pickle

class MemcachedAsyncCache(AsyncCache):
    async def initialize(self, host='localhost', port=11211):
        self.mc = aiomcache.Client(host, port)

    async def get(self, key):
        key_bytes = key.encode('utf-8')
        value = await self.mc.get(key_bytes)
        if value:
            return pickle.loads(value)
        return None

    async def set(self, key, value, ttl=None):
        key_bytes = key.encode('utf-8')
        ttl_value = ttl or self.ttl
        await self.mc.set(key_bytes, pickle.dumps(value), exptime=ttl_value)
```

## Performance Considerations

1. **Serialization**: Objects must be serialized before storage in external cache
   - Consider using msgpack or protobuf for better performance than pickle

2. **Network latency**: External cache has higher latency than in-memory
   - Use connection pooling
   - Consider caching frequently accessed data locally as well

3. **Key design**: Careful key design can improve cache efficiency
   - Use consistent naming conventions
   - Consider namespacing to avoid collisions

## Conclusion

By migrating to a distributed caching solution, Forge will gain:

- **Scalability**: Support for horizontal scaling across multiple instances
- **Consistency**: All instances share the same cache data
- **Resilience**: Cache survives individual instance restarts
- **Better resource utilization**: Cache size not limited by application server memory

This phased approach allows for a controlled transition while maintaining backward compatibility.
