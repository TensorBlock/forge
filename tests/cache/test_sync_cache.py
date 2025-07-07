#!/usr/bin/env python3
"""
Test script to verify all types of caching in the system.
Tests user cache, provider service cache, provider keys cache, and model list cache.
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

from app.core.cache import (
    Cache,
    invalidate_provider_models_cache,
    invalidate_user_cache_by_id,
    monitor_cache_performance,
    provider_service_cache,
    user_cache,
    warm_cache,
)
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

# Set environment variables before importing cache modules
os.environ["FORCE_MEMORY_CACHE"] = "true"
os.environ["DEBUG_CACHE"] = "true"


# Clear caches before each test
def setup_function(function):
    user_cache.clear()
    provider_service_cache.clear()
    ProviderService._models_cache = {}
    ProviderService._models_cache_expiry = {}
    ProviderService._models_l1_cache = {}


def test_basic_cache_operations():
    """Test basic cache operations"""
    print("\n🔍 TESTING BASIC CACHE OPERATIONS")
    print("================================")

    # Create a new cache instance
    cache = Cache(ttl_seconds=5)

    # Test set and get
    cache.set("test_key", "test_value")
    value = cache.get("test_key")
    assert value == "test_value", "Cache get/set failed"

    # Test TTL
    cache.set("expiring_key", "expiring_value", ttl=1)
    time.sleep(1.1)  # Wait for TTL to expire
    value = cache.get("expiring_key")
    assert value is None, "TTL expiration failed"

    # Test delete
    cache.set("delete_key", "delete_value")
    cache.delete("delete_key")
    value = cache.get("delete_key")
    assert value is None, "Cache delete failed"

    # Test clear
    cache.set("clear_key", "clear_value")
    cache.clear()
    value = cache.get("clear_key")
    assert value is None, "Cache clear failed"

    print("✅ Basic cache operations test passed")


def test_user_cache():
    """Test user caching functionality"""
    print("\n🔍 TESTING USER CACHE")
    print("====================")

    # Create mock user
    mock_user = User(
        id=1, email="test@example.com", username="testuser", is_active=True
    )

    # Test caching user
    api_key = "test_api_key_123"
    user_cache.set(f"user:{api_key}", mock_user)

    # Test retrieving from cache
    cached_user = user_cache.get(f"user:{api_key}")
    assert cached_user is not None, "User cache get failed"
    assert cached_user.id == mock_user.id, "Cached user ID mismatch"
    assert cached_user.email == mock_user.email, "Cached user email mismatch"

    # Test cache invalidation
    user_cache.delete(f"user:{api_key}")
    cached_user = user_cache.get(f"user:{api_key}")
    assert cached_user is None, "User cache invalidation failed"

    print("✅ User cache test passed")


def test_provider_keys_cache():
    """Test provider keys caching functionality"""
    print("\n🔍 TESTING PROVIDER KEYS CACHE")
    print("============================")

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
    provider_service_cache.set(cache_key, mock_keys, ttl=3600)

    # Test retrieving from cache
    cached_keys = provider_service_cache.get(cache_key)
    assert cached_keys is not None, "Provider keys cache get failed"
    assert "openai" in cached_keys, "OpenAI provider key missing from cache"
    assert "anthropic" in cached_keys, "Anthropic provider key missing from cache"
    assert (
        cached_keys["openai"]["model_mapping"]["gpt-4"] == "gpt-4-turbo"
    ), "Model mapping mismatch"

    # Test cache invalidation
    provider_service_cache.delete(cache_key)
    cached_keys = provider_service_cache.get(cache_key)
    assert cached_keys is None, "Provider keys cache invalidation failed"

    print("✅ Provider keys cache test passed")


def test_model_list_cache():
    """Test model list caching functionality"""
    print("\n🔍 TESTING MODEL LIST CACHE")
    print("=========================")

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
    cached_models = ProviderService.get_cached_models(provider_name, cache_key)
    assert cached_models is not None, "Model list cache get failed"
    assert len(cached_models) == EXPECTED_MODEL_COUNT, "Model list length mismatch"
    assert cached_models[FIRST_MODEL_INDEX]["id"] == "gpt-4", "Model ID mismatch"
    assert cached_models[SECOND_MODEL_INDEX]["id"] == "claude-3", "Model ID mismatch"

    # Test cache invalidation
    invalidate_provider_models_cache(provider_name)
    cached_models = ProviderService.get_cached_models(provider_name, cache_key)
    assert cached_models is None, "Model list cache invalidation failed"

    print("✅ Model list cache test passed")


def test_cache_invalidation():
    """Test cache invalidation scenarios"""
    print("\n🔍 TESTING CACHE INVALIDATION")
    print("===========================")

    # Test 1: User cache invalidation
    print("\n🔄 Test 1: User cache invalidation")
    mock_user = User(
        id=1, email="test@example.com", username="testuser", is_active=True
    )
    api_key = "test_api_key_123"

    # Set user in cache
    user_cache.set(f"user:{api_key}", mock_user)
    assert user_cache.get(f"user:{api_key}") is not None, "User cache set failed"

    # Invalidate user cache
    user_cache.delete(f"user:{api_key}")
    assert user_cache.get(f"user:{api_key}") is None, "User cache invalidation failed"

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
    provider_service_cache.set(cache_key, mock_keys, ttl=3600)
    assert (
        provider_service_cache.get(cache_key) is not None
    ), "Provider keys cache set failed"

    # Invalidate provider keys cache
    provider_service_cache.delete(cache_key)
    assert (
        provider_service_cache.get(cache_key) is None
    ), "Provider keys cache invalidation failed"

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
    ProviderService.cache_models(provider_name, model_cache_key, mock_models)
    assert (
        ProviderService.get_cached_models(provider_name, model_cache_key) is not None
    ), "Model list cache set failed"

    # Invalidate model list cache
    invalidate_provider_models_cache(provider_name)
    assert (
        ProviderService.get_cached_models(provider_name, model_cache_key) is None
    ), "Model list cache invalidation failed"


def test_cache_invalidation_by_id():
    """Test cache invalidation by user ID"""
    print("\nTesting cache invalidation by user ID...")

    # Create test user
    user = User(
        id=1,
        email="test@example.com",
        username="testuser",
        is_active=True,
        hashed_password="dummy_hash",
    )

    # Create test API keys
    api_key1 = "test_key_1"
    api_key2 = "test_key_2"

    # Cache user with multiple API keys
    user_cache.set(f"user:{api_key1}", user)
    user_cache.set(f"user:{api_key2}", user)

    # Verify user is cached
    cached_user1 = user_cache.get(f"user:{api_key1}")
    cached_user2 = user_cache.get(f"user:{api_key2}")
    assert cached_user1 is not None
    assert cached_user2 is not None
    assert cached_user1.id == user.id
    assert cached_user2.id == user.id

    # Invalidate all cache entries for this user
    invalidate_user_cache_by_id(user.id)

    # Verify cache is cleared
    assert user_cache.get(f"user:{api_key1}") is None
    assert user_cache.get(f"user:{api_key2}") is None


def test_provider_models_cache_invalidation():
    """Test provider models cache invalidation"""
    print("\nTesting provider models cache invalidation...")

    # Set up test data
    provider_name = "test_provider"
    models = [{"id": "model1"}, {"id": "model2"}]
    cache_key = "default"

    # Cache models using the public API
    ProviderService.cache_models(provider_name, cache_key, models)

    # Verify models are cached
    cached_models = ProviderService.get_cached_models(provider_name, cache_key)
    assert cached_models is not None
    assert len(cached_models) == 2
    assert cached_models[0]["id"] == "model1"
    assert cached_models[1]["id"] == "model2"

    # Invalidate cache
    invalidate_provider_models_cache(provider_name)

    # Verify cache is cleared
    cached_models = ProviderService.get_cached_models(provider_name, cache_key)
    assert cached_models is None, "Provider models cache invalidation failed"


def test_cache_stats_and_monitoring():
    """Test cache statistics and monitoring"""
    print("\n🔍 TESTING CACHE STATS AND MONITORING")
    print("===================================")

    # Test basic cache operations to generate stats
    cache = Cache(ttl_seconds=5)
    cache.set("test_key", "test_value")
    cache.get("test_key")  # Hit
    cache.get("nonexistent")  # Miss

    # Test stats
    stats = cache.stats()
    assert stats["hits"] == 1, "Cache hit count mismatch"
    assert stats["misses"] == 1, "Cache miss count mismatch"
    assert stats["total"] == 2, "Cache total count mismatch"
    assert stats["hit_rate"] == 0.5, "Cache hit rate mismatch"
    assert stats["entries"] == 1, "Cache entries count mismatch"

    # Test monitoring
    monitoring = monitor_cache_performance()
    assert "stats" in monitoring, "Cache stats missing"
    assert "overall_hit_rate" in monitoring, "Overall hit rate missing"
    assert "issues" in monitoring, "Issues list missing"

    print("✅ Cache stats and monitoring test passed")


async def test_cache_warming():
    """Test cache warming functionality"""
    print("\n🔍 TESTING CACHE WARMING")
    print("=======================")

    # Mock database session
    db = MagicMock()

    # Test cache warming
    await warm_cache(db)

    # Verify cache is populated
    assert user_cache.stats()["entries"] > 0, "User cache not warmed"
    assert (
        provider_service_cache.stats()["entries"] > 0
    ), "Provider service cache not warmed"

    print("✅ Cache warming test passed")
