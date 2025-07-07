import asyncio
import json
import os
import sys
from unittest import IsolatedAsyncioTestCase as TestCase
from unittest.mock import MagicMock, patch, AsyncMock

# Add the parent directory to the path so Python can find the app module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch bcrypt version detection to avoid warnings
import bcrypt

if not hasattr(bcrypt, "__about__"):
    import types

    bcrypt.__about__ = types.ModuleType("__about__")
    bcrypt.__about__.__version__ = (
        bcrypt.__version__ if hasattr(bcrypt, "__version__") else "3.2.0"
    )

from app.models.provider_key import ProviderKey
from app.models.user import User
from app.services.provider_service import ProviderService
from app.services.providers.adapter_factory import ProviderAdapterFactory
from app.core.cache import provider_service_cache, user_cache


class TestProviderServiceImages(TestCase):
    """Test cases for ProviderService images endpoints"""

    def setUp(self):
        # Mock user with provider keys
        self.user = MagicMock(spec=User)
        self.provider_key_openai = MagicMock(spec=ProviderKey)
        self.provider_key_openai.provider_name = "openai"
        self.provider_key_openai.encrypted_api_key = "encrypted_openai_key"
        self.provider_key_openai.base_url = None
        self.provider_key_openai.model_mapping = json.dumps({"dall-e-2": "dall-e-2"})

        self.provider_key_anthropic = MagicMock(spec=ProviderKey)
        self.provider_key_anthropic.provider_name = "anthropic"
        self.provider_key_anthropic.encrypted_api_key = "encrypted_anthropic_key"
        self.provider_key_anthropic.base_url = None
        self.provider_key_anthropic.model_mapping = json.dumps(
            {"custom-anthropic": "claude-3-opus", "claude-3-opus": "claude-3-opus"}
        )

        self.user.provider_keys = [
            self.provider_key_openai,
            self.provider_key_anthropic,
        ]

        # Mock DB
        self.db = MagicMock()

        # Clear caches
        provider_service_cache.clear()
        user_cache.clear()

        # Remove ProviderService creation from setUp
        # It will be created in each test after patching

    @patch(
        "app.services.usage_stats_service.UsageStatsService.log_api_request",
        return_value=None,
    )
    @patch("app.services.providers.adapter_factory.ProviderAdapterFactory.get_adapter")
    @patch("app.services.provider_service.decrypt_api_key")
    async def test_process_request_images_generations_routing(
        self, mock_decrypt, mock_get_adapter, mock_log_usage
    ):
        """Test images generation request routing based on model name"""

        # Create mocks for adapters
        mock_openai_adapter = MagicMock()
        mock_anthropic_adapter = MagicMock()
        # Mock decrypt_api_key to avoid actual decryption
        decrypt_key_map = {
            "encrypted_openai_key": "decrypted_openai_key",
            "encrypted_anthropic_key": "decrypted_anthropic_key",
        }
        mock_decrypt.side_effect = lambda key: decrypt_key_map[key]

        # Create the service with the NEW constructor signature (user.id)
        self.user.id = 1

        # Mock the database query that the new loading mechanism uses
        self.db.query.return_value.filter.return_value.all.return_value = [
            self.provider_key_openai,
            self.provider_key_anthropic,
        ]

        service = ProviderService(self.user.id, self.db)
        # Let the service load keys properly through the new mechanism
        service._load_provider_keys()

        # mock openai image generation response
        # no need to mock the response for anthropic
        mock_openai_adapter.process_image_generation = AsyncMock(return_value={"id": "openai-response"})

        # Configure get_adapter to return the appropriate mock
        provider_mapping = {
            "openai": mock_openai_adapter,
            "anthropic": mock_anthropic_adapter,
        }
        mock_get_adapter.side_effect = lambda provider, base_url, config: provider_mapping[
            provider
        ]

        # Test OpenAI routing
        result_openai =  await service.process_request("images/generations", {"model": "dall-e-2"})
        self.assertEqual(result_openai["id"], "openai-response")
        mock_openai_adapter.process_image_generation.assert_called_once()

        # Test Anthropic routing - should raise an exception since Anthropic doesn't support image generation
        mock_anthropic_adapter.process_image_generation.side_effect = ValueError(
            "Unsupported endpoint: images/generations for provider anthropic"
        )
        with self.assertRaises(ValueError) as context:
            await service.process_request(
                "images/generations", {"model": "claude-3-opus"}
            )
        self.assertEqual(
            str(context.exception),
            "Unsupported endpoint: images/generations for provider anthropic",
        )
        mock_anthropic_adapter.process_image_generation.assert_not_called()

    @patch(
        "app.services.usage_stats_service.UsageStatsService.log_api_request",
        return_value=None,
    )
    @patch("app.services.providers.adapter_factory.ProviderAdapterFactory.get_adapter")
    @patch("app.services.provider_service.decrypt_api_key")
    async def test_process_request_images_edits_routing(
        self, mock_decrypt, mock_get_adapter, mock_log_usage
    ):
        """Test images edits request routing based on model name"""

        # Create mocks for adapters
        mock_openai_adapter = MagicMock()
        mock_anthropic_adapter = MagicMock()
        # Mock decrypt_api_key to avoid actual decryption
        decrypt_key_map = {
            "encrypted_openai_key": "decrypted_openai_key",
            "encrypted_anthropic_key": "decrypted_anthropic_key",
        }
        mock_decrypt.side_effect = lambda key: decrypt_key_map[key]

        # Create the service with the NEW constructor signature (user.id)
        self.user.id = 1

        # Mock the database query that the new loading mechanism uses
        self.db.query.return_value.filter.return_value.all.return_value = [
            self.provider_key_openai,
            self.provider_key_anthropic,
        ]

        service = ProviderService(self.user.id, self.db)
        # Let the service load keys properly through the new mechanism
        service._load_provider_keys()

        # mock openai image edits response
        # no need to mock the response for anthropic
        mock_openai_adapter.process_image_edits = AsyncMock(return_value={"id": "openai-response"})

        # Configure get_adapter to return the appropriate mock
        provider_mapping = {
            "openai": mock_openai_adapter,
            "anthropic": mock_anthropic_adapter,
        }
        mock_get_adapter.side_effect = lambda provider, base_url, config: provider_mapping[
            provider
        ]

        # Test OpenAI routing
        result_openai = await service.process_request("images/edits", {"model": "dall-e-2"})
        self.assertEqual(result_openai["id"], "openai-response")
        mock_openai_adapter.process_image_edits.assert_called_once()

        # Test Anthropic routing - should raise an exception since Anthropic doesn't support image edits
        mock_anthropic_adapter.process_image_edits.side_effect = ValueError(
            "Unsupported endpoint: images/edits for provider anthropic"
        )
        with self.assertRaises(NotImplementedError) as context:
            await service.process_request("images/edits", {"model": "claude-3-opus"})
        self.assertEqual(
            str(context.exception),
            "Unsupported endpoint: images/edits for provider anthropic",
        )
        mock_anthropic_adapter.process_image_edits.assert_not_called()

    @patch("aiohttp.ClientSession.post")
    async def test_call_openai_process_image_generation(self, mock_post):
        """Test call to openai process_image_generation method"""

        # Get the adapter instance
        adapter = ProviderAdapterFactory.get_adapter("openai")

        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200

        # Create a mock coroutine for json() method
        async def mock_json():
            return {"id": "openai-response", "object": "image_generation"}

        mock_response.json = mock_json

        # Set up the mock context managers
        mock_post.return_value.__aenter__.return_value = mock_response

        # call the method and get the result
        result = await adapter.process_image_generation(
            "images/generations", {"model": "dall-e-2"}, "test-api-key"
        )

        # check result
        self.assertEqual(result["id"], "openai-response")
        self.assertEqual(result["object"], "image_generation")

        # verify the API was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-api-key")
        self.assertEqual(kwargs["json"]["model"], "dall-e-2")
        self.assertEqual(args[0], "https://api.openai.com/v1/images/generations")

    @patch("aiohttp.ClientSession.post")
    async def test_call_openai_process_image_edits(self, mock_post):
        """Test call to openai process_image_edits method"""

        # Get the adapter instance
        adapter = ProviderAdapterFactory.get_adapter("openai")

        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200

        # Create a mock coroutine for json() method
        async def mock_json():
            return {"id": "openai-response", "object": "image_edits"}

        mock_response.json = mock_json

        # Set up the mock context managers
        mock_post.return_value.__aenter__.return_value = mock_response

        # call the method and get the result
        result = await adapter.process_image_edits(
            "images/edits", {"model": "dall-e-2"}, "test-api-key"
        )

        # check result
        self.assertEqual(result["id"], "openai-response")
        self.assertEqual(result["object"], "image_edits")

        # verify the API was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-api-key")
        self.assertEqual(kwargs["json"]["model"], "dall-e-2")
        self.assertEqual(args[0], "https://api.openai.com/v1/images/edits")
