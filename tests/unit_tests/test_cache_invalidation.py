"""
Unit tests for cache invalidation behavior when Forge API key scope is updated.

Tests the fix for issue #8: Newly added provider not reflected in allowed provider list for Forge key
"""

import pytest
from unittest.mock import MagicMock, patch
from app.core.cache import invalidate_forge_scope_cache
from app.core.async_cache import invalidate_forge_scope_cache_async
import asyncio


class TestForgeKeyCacheInvalidation:
    """Test cache invalidation for Forge API keys"""

    def test_invalidate_forge_scope_cache_with_prefix(self):
        """Test that cache invalidation works correctly with forge- prefix"""
        # Mock the provider_service_cache
        with patch('app.core.cache.provider_service_cache') as mock_cache:
            # Test with full API key (including forge- prefix)
            full_api_key = "forge-abc123def456"
            
            invalidate_forge_scope_cache(full_api_key)
            
            # Should strip the "forge-" prefix when creating cache key
            expected_cache_key = "forge_scope:abc123def456"
            mock_cache.delete.assert_called_once_with(expected_cache_key)

    def test_invalidate_forge_scope_cache_without_prefix(self):
        """Test that cache invalidation works correctly without forge- prefix"""
        # Mock the provider_service_cache
        with patch('app.core.cache.provider_service_cache') as mock_cache:
            # Test with stripped API key (without forge- prefix)
            stripped_api_key = "abc123def456"
            
            invalidate_forge_scope_cache(stripped_api_key)
            
            # Should use the key as-is when creating cache key
            expected_cache_key = "forge_scope:abc123def456"
            mock_cache.delete.assert_called_once_with(expected_cache_key)

    def test_invalidate_forge_scope_cache_empty_key(self):
        """Test that cache invalidation handles empty keys gracefully"""
        # Mock the provider_service_cache
        with patch('app.core.cache.provider_service_cache') as mock_cache:
            # Test with empty API key
            invalidate_forge_scope_cache("")
            
            # Should not call delete for empty keys
            mock_cache.delete.assert_not_called()

    def test_invalidate_forge_scope_cache_none_key(self):
        """Test that cache invalidation handles None keys gracefully"""
        # Mock the provider_service_cache
        with patch('app.core.cache.provider_service_cache') as mock_cache:
            # Test with None API key
            invalidate_forge_scope_cache(None)
            
            # Should not call delete for None keys
            mock_cache.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_forge_scope_cache_async_with_prefix(self):
        """Test that async cache invalidation works correctly with forge- prefix"""
        # Mock the async_provider_service_cache
        with patch('app.core.async_cache.async_provider_service_cache') as mock_cache:
            from unittest.mock import AsyncMock
            mock_cache.delete = AsyncMock()
            
            # Test with full API key (including forge- prefix)
            full_api_key = "forge-abc123def456"
            
            await invalidate_forge_scope_cache_async(full_api_key)
            
            # Should strip the "forge-" prefix when creating cache key
            expected_cache_key = "forge_scope:abc123def456"
            mock_cache.delete.assert_called_once_with(expected_cache_key)

    @pytest.mark.asyncio
    async def test_invalidate_forge_scope_cache_async_without_prefix(self):
        """Test that async cache invalidation works correctly without forge- prefix"""
        # Mock the async_provider_service_cache
        with patch('app.core.async_cache.async_provider_service_cache') as mock_cache:
            from unittest.mock import AsyncMock
            mock_cache.delete = AsyncMock()
            
            # Test with stripped API key (without forge- prefix)
            stripped_api_key = "abc123def456"
            
            await invalidate_forge_scope_cache_async(stripped_api_key)
            
            # Should use the key as-is when creating cache key
            expected_cache_key = "forge_scope:abc123def456"
            mock_cache.delete.assert_called_once_with(expected_cache_key)

    def test_cache_key_format_consistency(self):
        """Test that cache invalidation uses the same key format as cache setting"""
        # This test verifies the fix for issue #8
        # The bug was that cache was set with stripped key but invalidated with full key
        
        with patch('app.core.cache.provider_service_cache') as mock_cache:
            # Simulate the DB key format (with forge- prefix)
            db_api_key = "forge-d8fc7c26e350771b28fe94b7"
            
            # When we invalidate using the DB key
            invalidate_forge_scope_cache(db_api_key)
            
            # It should create the same cache key format used by get_user_by_api_key
            # which strips the forge- prefix: api_key = api_key_from_header[6:]
            stripped_key = db_api_key[6:]  # Remove "forge-" prefix
            expected_cache_key = f"forge_scope:{stripped_key}"
            
            mock_cache.delete.assert_called_once_with(expected_cache_key)
            
            # Verify the exact cache key format
            assert expected_cache_key == "forge_scope:d8fc7c26e350771b28fe94b7" 