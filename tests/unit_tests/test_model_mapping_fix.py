import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.provider_service import ProviderService
from app.models.provider_key import ProviderKey
from app.models.user import User


class TestModelMappingFix:
    """Test cases for the model_mapping string-to-dict conversion fix."""

    def test_ensure_model_mapping_dict_helper(self):
        """Test the _ensure_model_mapping_dict helper method with various inputs."""
        # Create a ProviderService instance (db can be None for this test)
        ps = ProviderService(1, None)
        
        # Test valid JSON string
        result = ps._ensure_model_mapping_dict('{"gpt-4": "gpt-4-turbo", "claude": "claude-3-opus"}')
        assert result == {"gpt-4": "gpt-4-turbo", "claude": "claude-3-opus"}
        
        # Test empty string
        result = ps._ensure_model_mapping_dict("")
        assert result == {}
        
        # Test None
        result = ps._ensure_model_mapping_dict(None)
        assert result == {}
        
        # Test already valid dict
        test_dict = {"test": "value"}
        result = ps._ensure_model_mapping_dict(test_dict)
        assert result == test_dict
        assert result is test_dict  # Should return the same object
        
        # Test invalid JSON string
        result = ps._ensure_model_mapping_dict('{invalid json}')
        assert result == {}
        
        # Test malformed JSON string
        result = ps._ensure_model_mapping_dict('{"key": "value",}')
        assert result == {}
        
        # Test non-string, non-dict input
        result = ps._ensure_model_mapping_dict(123)
        assert result == {}
        
        result = ps._ensure_model_mapping_dict([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_list_models_with_string_model_mapping(self):
        """Test that list_models works correctly when model_mapping is stored as a string."""
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        # Mock user
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        
        # Create ProviderService instance
        ps = ProviderService(1, mock_db)
        
        # Mock the database query to return a provider key with string model_mapping
        mock_provider_key = MagicMock(spec=ProviderKey)
        mock_provider_key.provider_name = "openai"
        mock_provider_key.encrypted_api_key = "encrypted_key"
        mock_provider_key.base_url = "https://api.openai.com"
        # This simulates old data where model_mapping was stored as a string
        mock_provider_key.model_mapping = '{"gpt-4": "gpt-4-turbo"}'
        
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_provider_key]
        mock_db.execute.return_value = mock_result
        
        # Mock the cache to return None (no cached data)
        ps._keys_loaded = False
        
        # Mock the provider adapter
        mock_adapter = MagicMock()
        mock_adapter.list_models = AsyncMock(return_value=["gpt-4", "gpt-3.5-turbo"])
        
        # Mock the adapter factory
        with pytest.MonkeyPatch().context() as m:
            m.setattr("app.services.provider_service.ProviderAdapterFactory.get_adapter_cls", 
                     lambda x: MagicMock(deserialize_api_key_config=lambda x: ("api_key", {})))
            m.setattr("app.services.provider_service.ProviderAdapterFactory.get_adapter", 
                     lambda x, y, z: mock_adapter)
            m.setattr("app.services.provider_service.decrypt_api_key", lambda x: "decrypted_key")
            m.setattr("app.services.provider_service.async_provider_service_cache.get", 
                     AsyncMock(return_value=None))
            m.setattr("app.services.provider_service.async_provider_service_cache.set", 
                     AsyncMock())
            
            # Call list_models - this should not raise an error
            result = await ps.list_models()
            
            # Verify the result
            assert isinstance(result, list)
            assert len(result) == 2  # Two models returned
            
            # Verify the models have the correct structure
            for model in result:
                assert "id" in model
                assert "display_name" in model
                assert "object" in model
                assert "owned_by" in model
                assert model["object"] == "model"
                assert model["owned_by"] == "openai"

    @pytest.mark.asyncio
    async def test_list_models_with_invalid_json_string(self):
        """Test that list_models handles invalid JSON strings gracefully."""
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        # Mock user
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        
        # Create ProviderService instance
        ps = ProviderService(1, mock_db)
        
        # Mock the database query to return a provider key with invalid JSON string
        mock_provider_key = MagicMock(spec=ProviderKey)
        mock_provider_key.provider_name = "openai"
        mock_provider_key.encrypted_api_key = "encrypted_key"
        mock_provider_key.base_url = "https://api.openai.com"
        # This simulates corrupted data
        mock_provider_key.model_mapping = '{invalid json string'
        
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_provider_key]
        mock_db.execute.return_value = mock_result
        
        # Mock the cache to return None (no cached data)
        ps._keys_loaded = False
        
        # Mock the provider adapter
        mock_adapter = MagicMock()
        mock_adapter.list_models = AsyncMock(return_value=["gpt-4", "gpt-3.5-turbo"])
        
        # Mock the adapter factory
        with pytest.MonkeyPatch().context() as m:
            m.setattr("app.services.provider_service.ProviderAdapterFactory.get_adapter_cls", 
                     lambda x: MagicMock(deserialize_api_key_config=lambda x: ("api_key", {})))
            m.setattr("app.services.provider_service.ProviderAdapterFactory.get_adapter", 
                     lambda x, y, z: mock_adapter)
            m.setattr("app.services.provider_service.decrypt_api_key", lambda x: "decrypted_key")
            m.setattr("app.services.provider_service.async_provider_service_cache.get", 
                     AsyncMock(return_value=None))
            m.setattr("app.services.provider_service.async_provider_service_cache.set", 
                     AsyncMock())
            
            # Call list_models - this should not raise an error
            result = await ps.list_models()
            
            # Verify the result
            assert isinstance(result, list)
            assert len(result) == 2  # Two models returned
            
            # Since model_mapping was invalid, display_name should be the same as the model name
            for model in result:
                assert model["display_name"] == model["id"].split("/")[1]

    @pytest.mark.asyncio
    async def test_list_models_with_none_model_mapping(self):
        """Test that list_models works correctly when model_mapping is None."""
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        # Mock user
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        
        # Create ProviderService instance
        ps = ProviderService(1, mock_db)
        
        # Mock the database query to return a provider key with None model_mapping
        mock_provider_key = MagicMock(spec=ProviderKey)
        mock_provider_key.provider_name = "openai"
        mock_provider_key.encrypted_api_key = "encrypted_key"
        mock_provider_key.base_url = "https://api.openai.com"
        mock_provider_key.model_mapping = None
        
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_provider_key]
        mock_db.execute.return_value = mock_result
        
        # Mock the cache to return None (no cached data)
        ps._keys_loaded = False
        
        # Mock the provider adapter
        mock_adapter = MagicMock()
        mock_adapter.list_models = AsyncMock(return_value=["gpt-4", "gpt-3.5-turbo"])
        
        # Mock the adapter factory
        with pytest.MonkeyPatch().context() as m:
            m.setattr("app.services.provider_service.ProviderAdapterFactory.get_adapter_cls", 
                     lambda x: MagicMock(deserialize_api_key_config=lambda x: ("api_key", {})))
            m.setattr("app.services.provider_service.ProviderAdapterFactory.get_adapter", 
                     lambda x, y, z: mock_adapter)
            m.setattr("app.services.provider_service.decrypt_api_key", lambda x: "decrypted_key")
            m.setattr("app.services.provider_service.async_provider_service_cache.get", 
                     AsyncMock(return_value=None))
            m.setattr("app.services.provider_service.async_provider_service_cache.set", 
                     AsyncMock())
            
            # Call list_models - this should not raise an error
            result = await ps.list_models()
            
            # Verify the result
            assert isinstance(result, list)
            assert len(result) == 2  # Two models returned
            
            # Since model_mapping was None, display_name should be the same as the model name
            for model in result:
                assert model["display_name"] == model["id"].split("/")[1]

    def test_get_provider_info_with_string_model_mapping(self):
        """Test that _get_provider_info_with_prefix works with string model_mapping."""
        ps = ProviderService(1, None)
        
        # Mock provider_keys with string model_mapping
        ps.provider_keys = {
            "openai": {
                "api_key": "test_key",
                "base_url": "https://api.openai.com",
                "model_mapping": '{"custom-gpt": "gpt-4"}'
            }
        }
        ps._keys_loaded = True
        
        # Test that it works correctly
        provider_name, mapped_model, base_url = ps._get_provider_info_with_prefix(
            "openai", "custom-gpt", "openai/custom-gpt"
        )
        
        assert provider_name == "openai"
        assert mapped_model == "gpt-4"  # Should be mapped correctly
        assert base_url == "https://api.openai.com"

    def test_find_provider_for_unprefixed_model_with_string_model_mapping(self):
        """Test that _find_provider_for_unprefixed_model works with string model_mapping."""
        ps = ProviderService(1, None)
        
        # Mock provider_keys with string model_mapping
        ps.provider_keys = {
            "openai": {
                "api_key": "test_key",
                "base_url": "https://api.openai.com",
                "model_mapping": '{"custom-gpt": "gpt-4"}'
            }
        }
        ps._keys_loaded = True
        
        # Test that it works correctly
        provider_name, mapped_model, base_url = ps._find_provider_for_unprefixed_model("custom-gpt")
        
        assert provider_name == "openai"
        assert mapped_model == "gpt-4"  # Should be mapped correctly
        assert base_url == "https://api.openai.com"

    def test_original_error_scenario_prevention(self):
        """Test that the original 'str' object has no attribute 'items' error is prevented."""
        ps = ProviderService(1, None)
        
        # Simulate the exact scenario that caused the original error
        # This would have caused the error before our fix
        provider_data = {
            "base_url": "https://api.openai.com",
            "model_mapping": '{"gpt-4": "gpt-4-turbo"}'  # String instead of dict
        }
        
        # This line would have failed before our fix:
        # cache_key = f"{base_url}:{hash(frozenset(provider_data.get('model_mapping', {}).items()))}"
        # Because provider_data.get('model_mapping', {}) would return a string, and strings don't have .items()
        
        # Now with our fix, this should work:
        base_url = provider_data.get("base_url", "default")
        model_mapping = ps._ensure_model_mapping_dict(provider_data.get("model_mapping", {}))
        cache_key = f"{base_url}:{hash(frozenset(model_mapping.items()))}"
        
        # Verify that no error was raised and we got a valid cache key
        assert isinstance(cache_key, str)
        assert "https://api.openai.com" in cache_key
        assert len(cache_key) > 0

    def test_cache_key_generation_with_various_model_mappings(self):
        """Test that cache key generation works with various model_mapping types."""
        ps = ProviderService(1, None)
        
        test_cases = [
            # (model_mapping, expected_type)
            ('{"gpt-4": "gpt-4-turbo"}', dict),
            ('', dict),
            (None, dict),
            ('{invalid json}', dict),
            ({"valid": "dict"}, dict),
        ]
        
        for model_mapping, expected_type in test_cases:
            result = ps._ensure_model_mapping_dict(model_mapping)
            assert isinstance(result, expected_type)
            
            # Test that we can call .items() on the result
            items = result.items()
            assert hasattr(items, '__iter__')  # Should be iterable
            
            # Test cache key generation
            base_url = "https://api.openai.com"
            cache_key = f"{base_url}:{hash(frozenset(result.items()))}"
            assert isinstance(cache_key, str)
            assert base_url in cache_key 