#!/usr/bin/env python3
"""
Test script to verify all types of async caching in the system.
Tests user cache, provider service cache, provider keys cache, and model list cache.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import delete

from app.core.async_cache import (
    AsyncCache,
    async_cached,
    async_provider_service_cache,
    async_user_cache,
    cache_user_async,
    get_cache_stats_async,
    get_cached_user_async,
    invalidate_provider_models_cache_async,
    invalidate_user_cache_by_id_async,
    monitor_cache_performance_async,
    warm_cache_async,
)
from app.core.security import encrypt_api_key
from app.models.provider_key import ProviderKey
from app.models.user import User
from app.services.provider_service import ProviderService

# Add constants at the top of the file, after imports
EXPECTED_MODEL_COUNT = 2  # Expected number of models in test data
FIRST_MODEL_INDEX = 0  # Index of first model in test data
SECOND_MODEL_INDEX = 1  # Index of second model in test data

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Change to the project root directory
os.chdir(script_dir)

# Ensure DEBUG_CACHE is enabled
os.environ["DEBUG_CACHE"] = "true"


async def test_basic_async_cache_operations():
    """Test basic async cache operations"""
    print("\n🔍 TESTING BASIC ASYNC CACHE OPERATIONS")
    print("======================================")

    # Create a new cache instance
    cache = AsyncCache(ttl_seconds=5)

    # Test set and get
    await cache.set("test_key", "test_value")
    value = await cache.get("test_key")
    assert value == "test_value", "Async cache get/set failed"

    # Test TTL
    await cache.set("expiring_key", "expiring_value", ttl=1)
    await asyncio.sleep(1.1)  # Wait for TTL to expire
    value = await cache.get("expiring_key")
    assert value is None, "Async cache TTL expiration failed"

    # Test delete
    await cache.set("delete_key", "delete_value")
    await cache.delete("delete_key")
    value = await cache.get("delete_key")
    assert value is None, "Async cache delete failed"

    # Test clear
    await cache.set("clear_key", "clear_value")
    await cache.clear()
    value = await cache.get("clear_key")
    assert value is None, "Async cache clear failed"

    print("✅ Basic async cache operations test passed")
    return True


async def test_user_async_cache():
    """Test async user caching functionality"""
    print("\n🔍 TESTING ASYNC USER CACHE")
    print("==========================")

    # Clear user cache
    await async_user_cache.clear()

    # Create mock user
    mock_user = User(
        id=1,
        email="test@example.com",
        username="testuser",
        is_active=True,
        hashed_password="dummy_hash",
    )

    # Test caching user
    api_key = "test_api_key_123"
    await async_user_cache.set(f"user:{api_key}", mock_user)

    # Test retrieving from cache
    cached_user = await async_user_cache.get(f"user:{api_key}")
    assert cached_user is not None, "Async user cache get failed"
    assert cached_user.id == mock_user.id, "Cached user ID mismatch"
    assert cached_user.email == mock_user.email, "Cached user email mismatch"

    # Test cache invalidation
    await async_user_cache.delete(f"user:{api_key}")
    cached_user = await async_user_cache.get(f"user:{api_key}")
    assert cached_user is None, "Async user cache invalidation failed"

    print("✅ Async user cache test passed")
    return True


async def test_provider_keys_async_cache():
    """Test async provider keys caching functionality"""
    print("\n🔍 TESTING ASYNC PROVIDER KEYS CACHE")
    print("==================================")

    # Clear provider service cache
    await async_provider_service_cache.clear()

    # Create mock provider keys
    mock_keys = {
        "openai": {
            "api_key": "sk_test_123",
            "base_url": "https://api.openai.com/v1",
            "model_mapping": {"gpt-4": "gpt-4-turbo"},
        },
        "anthropic": {
            "api_key": "sk-ant-test-123",
            "base_url": "https://api.anthropic.com/v1",
            "model_mapping": {},
        },
    }

    # Test caching provider keys
    user_id = 1
    cache_key = f"provider_keys:{user_id}"
    await async_provider_service_cache.set(cache_key, mock_keys, ttl=3600)

    # Test retrieving from cache
    cached_keys = await async_provider_service_cache.get(cache_key)
    assert cached_keys is not None, "Async provider keys cache get failed"
    assert "openai" in cached_keys, "OpenAI provider key missing from cache"
    assert "anthropic" in cached_keys, "Anthropic provider key missing from cache"
    assert (
        cached_keys["openai"]["model_mapping"]["gpt-4"] == "gpt-4-turbo"
    ), "Model mapping mismatch"

    # Test cache invalidation
    await async_provider_service_cache.delete(cache_key)
    cached_keys = await async_provider_service_cache.get(cache_key)
    assert cached_keys is None, "Async provider keys cache invalidation failed"

    print("✅ Async provider keys cache test passed")
    return True


async def test_model_list_async_cache():
    """Test async model list caching functionality"""
    print("\n🔍 TESTING ASYNC MODEL LIST CACHE")
    print("================================")

    # Create mock model list
    mock_models = [
        {
            "id": "gpt-4",
            "display_name": "GPT-4",
            "object": "model",
            "owned_by": "openai",
        },
        {
            "id": "claude-3",
            "display_name": "Claude 3",
            "object": "model",
            "owned_by": "anthropic",
        },
    ]

    # Test caching models
    provider_name = "openai"
    cache_key = "default"
    ProviderService.cache_models(provider_name, cache_key, mock_models)

    # Test retrieving from cache
    cached_models = await ProviderService.get_cached_models(provider_name, cache_key)
    assert cached_models is not None, "Async model list cache get failed"
    assert len(cached_models) == EXPECTED_MODEL_COUNT, "Model list length mismatch"
    assert cached_models[FIRST_MODEL_INDEX]["id"] == "gpt-4", "Model ID mismatch"
    assert cached_models[SECOND_MODEL_INDEX]["id"] == "claude-3", "Model ID mismatch"

    # Test cache invalidation
    ProviderService._models_cache = {}
    ProviderService._models_cache_expiry = {}
    cached_models = await ProviderService.get_cached_models(provider_name, cache_key)
    assert cached_models is None, "Async model list cache invalidation failed"

    print("✅ Async model list cache test passed")
    return True


# Test class with cached methods
class MockTestService:
    def __init__(self, id):
        self.id = id
        self.counter = 0

    @async_cached(AsyncCache())
    async def slow_operation(self, param):
        """Simulate a slow operation that benefits from caching"""
        self.counter += 1
        await asyncio.sleep(0.1)  # Simulate network or DB delay
        return f"Result for {param} (call {self.counter})"


async def test_async_cache_decorator():
    """Test the async_cached decorator"""
    print("\n🔍 TESTING ASYNC CACHE DECORATOR")
    print("===============================")

    test_service = MockTestService(1)

    print("\n🔄 Test 1: First call (should be a cache miss)")
    start_time = time.time()
    result1 = await test_service.slow_operation("test")
    elapsed1 = time.time() - start_time
    print(f"  ⏱️  Time: {elapsed1:.6f} seconds")
    print(f"  📋 Result: {result1}")

    print("\n🔄 Test 2: Second call with same param (should be a cache hit)")
    start_time = time.time()
    result2 = await test_service.slow_operation("test")
    elapsed2 = time.time() - start_time
    print(f"  ⏱️  Time: {elapsed2:.6f} seconds")
    print(f"  📋 Result: {result2}")

    print("\n🔄 Test 3: Call with different param (should be a cache miss)")
    start_time = time.time()
    result3 = await test_service.slow_operation("other")
    elapsed3 = time.time() - start_time
    print(f"  ⏱️  Time: {elapsed3:.6f} seconds")
    print(f"  📋 Result: {result3}")

    # Calculate speed improvement
    if elapsed1 > 0 and elapsed2 > 0:
        speedup = elapsed1 / elapsed2
        print(f"\n🚀 Cache speedup: {speedup:.2f}x faster with caching")

    return True


async def test_provider_service_async():
    """Test the async_get_instance method of ProviderService"""
    print("\n🔍 TESTING PROVIDER SERVICE ASYNC CACHE")
    print("=====================================")

    # Clear cache first
    await async_provider_service_cache.clear()

    # Create mock user and db
    mock_user = MagicMock(id=1)
    mock_db = MagicMock()

    print("\n🔄 Test 1: First instance creation (should be a cache miss)")
    start_time = time.time()
    service1 = await ProviderService.async_get_instance(mock_user, mock_db)
    elapsed1 = time.time() - start_time
    print(f"  ⏱️  Time to get first instance: {elapsed1:.6f} seconds")

    print("\n🔄 Test 2: Second request (should be a cache hit)")
    start_time = time.time()
    service2 = await ProviderService.async_get_instance(mock_user, mock_db)
    elapsed2 = time.time() - start_time
    print(f"  ⏱️  Time to get second instance: {elapsed2:.6f} seconds")

    # Check if instances are the same object
    print("\n🔍 Verifying instance identity")
    print(f"  Instance 1 ID: {id(service1)}")
    print(f"  Instance 2 ID: {id(service2)}")
    print(f"  Instances are the same object: {service1 is service2}")

    # Calculate speed improvement
    if elapsed1 > 0 and elapsed2 > 0:
        speedup = elapsed1 / elapsed2
        print(f"\n🚀 Cache speedup: {speedup:.2f}x faster with caching")

    return True


async def test_async_cache_invalidation():
    """Test async cache invalidation scenarios"""
    print("\n🔍 TESTING ASYNC CACHE INVALIDATION")
    print("================================")

    # Create cache instances
    await async_user_cache.clear()
    await async_provider_service_cache.clear()

    # Test 1: User cache invalidation
    print("\n🔄 Test 1: User cache invalidation")
    mock_user = User(
        id=1, email="test@example.com", username="testuser", is_active=True
    )
    api_key = "test_api_key_123"

    # Set user in cache
    await async_user_cache.set(f"user:{api_key}", mock_user)
    cached_user = await async_user_cache.get(f"user:{api_key}")
    assert cached_user is not None, "User cache set failed"

    # Invalidate user cache
    await async_user_cache.delete(f"user:{api_key}")
    cached_user = await async_user_cache.get(f"user:{api_key}")
    assert cached_user is None, "User cache invalidation failed"

    # Test 2: Provider keys cache invalidation
    print("\n🔄 Test 2: Provider keys cache invalidation")
    mock_keys = {
        "openai": {
            "api_key": "sk_test_123",
            "base_url": "https://api.openai.com/v1",
            "model_mapping": {"gpt-4": "gpt-4-turbo"},
        }
    }
    user_id = 1
    cache_key = f"provider_keys:{user_id}"

    # Set provider keys in cache
    await async_provider_service_cache.set(cache_key, mock_keys, ttl=3600)
    cached_keys = await async_provider_service_cache.get(cache_key)
    assert cached_keys is not None, "Provider keys cache set failed"

    # Invalidate provider keys cache
    await async_provider_service_cache.delete(cache_key)
    cached_keys = await async_provider_service_cache.get(cache_key)
    assert cached_keys is None, "Provider keys cache invalidation failed"

    # Test 3: Model list cache invalidation
    print("\n🔄 Test 3: Model list cache invalidation")
    mock_models = [
        {
            "id": "gpt-4",
            "display_name": "GPT-4",
            "object": "model",
            "owned_by": "openai",
        }
    ]
    provider_name = "openai"
    model_cache_key = "default"

    # Set model list in cache
    await ProviderService.cache_models(provider_name, model_cache_key, mock_models)
    cached_models = await ProviderService.get_cached_models(provider_name, model_cache_key)
    assert cached_models is not None, "Model list cache set failed"

    # Invalidate model list cache
    ProviderService._models_cache = {}
    ProviderService._models_cache_expiry = {}
    cached_models = await ProviderService.get_cached_models(provider_name, model_cache_key)
    assert cached_models is None, "Model list cache invalidation failed"

    # Test 4: Provider service instance cache invalidation
    print("\n🔄 Test 4: Provider service instance cache invalidation")
    mock_user = MagicMock(id=1)
    mock_db = MagicMock()

    # Clear any existing instances
    await async_provider_service_cache.clear()

    # Get first instance (should be cached)
    service1 = await ProviderService.async_get_instance(mock_user, mock_db)
    assert service1 is not None, "Provider service instance creation failed"

    # Invalidate provider service cache
    await async_provider_service_cache.clear()

    # Get new instance (should be different)
    service2 = await ProviderService.async_get_instance(mock_user, mock_db)
    assert (
        service2 is not None
    ), "Provider service instance creation failed after invalidation"
    assert service1 is not service2, "Provider service cache invalidation failed"

    # Test 5: TTL-based invalidation
    print("\n🔄 Test 5: TTL-based invalidation")
    # Set value with short TTL
    await async_provider_service_cache.set("ttl_test", "value", ttl=1)
    cached_value = await async_provider_service_cache.get("ttl_test")
    assert cached_value == "value", "TTL cache set failed"

    # Wait for TTL to expire
    await asyncio.sleep(1.1)
    cached_value = await async_provider_service_cache.get("ttl_test")
    assert cached_value is None, "TTL-based invalidation failed"

    print("✅ Async cache invalidation tests passed")
    return True


async def test_async_cache_invalidation_by_id():
    """Test async cache invalidation by user ID"""
    print("\nTesting async cache invalidation by user ID...")

    # Create test user
    user = User(
        id=1,
        email="test@example.com",
        username="testuser",
        is_active=True,
        hashed_password="dummy_hash",
    )

    # Cache user with multiple API keys
    await cache_user_async("key1", user)
    await cache_user_async("key2", user)

    # Verify user is cached
    cached_user1 = await get_cached_user_async("key1")
    cached_user2 = await get_cached_user_async("key2")
    assert cached_user1 is not None
    assert cached_user2 is not None
    assert cached_user1.id == user.id
    assert cached_user2.id == user.id

    # Invalidate all cache entries for this user
    await invalidate_user_cache_by_id_async(user.id)

    # Verify cache is cleared
    assert await get_cached_user_async("key1") is None
    assert await get_cached_user_async("key2") is None

    return True


async def test_async_provider_models_cache_invalidation():
    """Test async provider models cache invalidation"""
    print("\nTesting async provider models cache invalidation...")

    # Import here to avoid circular imports
    from app.services.provider_service import ProviderService

    # Set up test data
    provider_name = "test_provider"
    models = ["model1", "model2"]

    # Cache models
    ProviderService._models_cache[provider_name] = models
    ProviderService._models_cache_expiry[provider_name] = time.time() + 3600

    # Verify models are cached
    assert provider_name in ProviderService._models_cache
    assert provider_name in ProviderService._models_cache_expiry

    # Invalidate cache
    await invalidate_provider_models_cache_async(provider_name)

    # Verify cache is cleared
    assert provider_name not in ProviderService._models_cache
    assert provider_name not in ProviderService._models_cache_expiry

    return True


async def test_async_cache_stats_and_monitoring():
    """Test async cache statistics and monitoring"""
    print("\nTesting async cache statistics and monitoring...")

    # Clear caches first
    await async_user_cache.clear()
    await async_provider_service_cache.clear()

    # Add some test data
    user = User(
        id=1,
        email="test@example.com",
        username="testuser",
        is_active=True,
        hashed_password="dummy_hash",
    )
    await cache_user_async("test_key", user)

    # Get cache stats
    stats = await get_cache_stats_async()
    assert "user_cache" in stats
    assert "provider_service_cache" in stats
    assert stats["user_cache"]["entries"] == 1
    assert stats["user_cache"]["hits"] >= 0
    assert stats["user_cache"]["misses"] >= 0

    # Test cache monitoring
    metrics = await monitor_cache_performance_async()
    assert "stats" in metrics
    assert "overall_hit_rate" in metrics
    assert "issues" in metrics
    assert isinstance(metrics["overall_hit_rate"], float)
    assert isinstance(metrics["issues"], list)

    return True


async def test_async_cache_warming():
    """Test async cache warming functionality"""
    print("\nTesting async cache warming...")

    # Create test database session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    from app.models.base import Base

    # Use SQLite in-memory database for testing
    engine = create_async_engine("sqlite:///:memory:")

    # Create all tables
    Base.metadata.create_all(bind=engine)

    testing = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
    async with testing() as db:
        try:
            # Create test user and API key
            user = User(
                email="test@example.com",
                username="testuser",
                is_active=True,
                hashed_password="dummy_hash",
            )
            db.add(user)
            db.commit()

            # Create a test API key
            test_api_key = "test_key_123"
            encrypted_key = encrypt_api_key(test_api_key)

            provider_key = ProviderKey(
                user_id=user.id,
                provider_name="test_provider",
                encrypted_api_key=encrypted_key,
            )
            db.add(provider_key)
            db.commit()

            # Warm the cache
            await warm_cache_async(db)

            # Verify user is cached with the correct API key
            cached_user = await get_cached_user_async(test_api_key)
            assert cached_user is not None
            assert cached_user.id == user.id

        finally:
            # Clean up
            await db.execute(delete(ProviderKey))
            await db.execute(delete(User))
            await db.commit()
            # Drop all tables
            Base.metadata.drop_all(bind=engine)

    return True
