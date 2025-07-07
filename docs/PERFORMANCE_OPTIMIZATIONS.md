# Performance Optimizations for Forge

This document outlines the performance optimizations implemented in the Forge application to enhance scalability, reduce database load, and improve response times.

## Key Optimizations

### 1. Multi-Level Caching

We've implemented several caching mechanisms to reduce redundant operations:

#### User Authentication Cache
- Each API request requires user authentication via their API key
- Instead of querying the database for every request, users are now cached for 5 minutes
- Significant reduction in database reads for high-traffic users

#### Provider Service Caching
- ProviderService instances are now reused across requests for the same user
- Cached for 10 minutes to balance memory usage with performance
- Avoids redundant instantiation and database reads

#### Provider API Key Caching
- API keys are now lazy-loaded and decrypted only when needed
- Once decrypted, they remain available in the cached service instance
- Eliminates repeated decryption operations which are computationally expensive

#### Model List Caching
- Models returned by providers are cached for 1 hour
- Avoids repeated API calls to list models, which can be rate-limited by providers
- Each provider/configuration has its own cache entry

### 2. Lazy Loading

- Provider keys are not loaded during service initialization
- Keys are only loaded and decrypted when needed for a request
- If a request doesn't need access to provider keys, no decryption occurs

### 3. Cache Invalidation

We've implemented targeted cache invalidation to ensure data consistency:

- User cache is invalidated when:
  - User details are updated
  - User's Forge API key is reset

- Provider service cache is invalidated when:
  - Provider keys are added
  - Provider keys are updated
  - Provider keys are deleted
  - User details change

### 4. Error Resilience

- Model listing now has error handling to prevent failures if one provider API is down
- Batch processing of concurrent API requests to avoid overwhelming provider APIs

## Implementation Details

### Cache Implementation

A simple in-memory cache with time-to-live (TTL) expiration:
- `app/core/cache.py` contains the cache implementation
- Each cache entry has its own expiration time
- Cache entries are automatically removed when accessed after expiration

### Adapter Caching

Provider adapters are cached at the class level:
- Adapters are stateless and can be reused across all requests
- Improves memory usage by sharing adapter instances

### Service Reuse Pattern

The ProviderService now uses a factory pattern:
- `get_instance()` method returns cached instances when available
- Creates new instances only when needed

## Performance Impact

These optimizations significantly reduce:
- Database queries per request
- Decryption operations
- Memory usage
- API calls to providers

This results in:
- Lower response times
- Higher maximum throughput
- Reduced database load
- Better scalability

## Future Improvements

Potential future optimizations:
- Distributed caching (Redis) for multi-server deployments
- More granular cache expiration policies
- Request batching for similar consecutive requests
- Advanced monitoring of cache hit/miss rates
