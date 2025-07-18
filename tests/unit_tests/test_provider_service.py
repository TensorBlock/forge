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
from app.core.async_cache import async_provider_service_cache, async_user_cache


class TestProviderService(TestCase):
    """Test the provider service"""

    async def asyncSetUp(self):
        # Reset the adapters cache
        ProviderService._adapters_cache = {}

        # Mock user with provider keys
        self.user = MagicMock(spec=User)
        self.provider_key_openai = MagicMock(spec=ProviderKey)
        self.provider_key_openai.provider_name = "openai"
        self.provider_key_openai.encrypted_api_key = "encrypted_openai_key"
        self.provider_key_openai.base_url = None
        self.provider_key_openai.model_mapping = json.dumps({"custom-gpt": "gpt-4"})

        self.provider_key_anthropic = MagicMock(spec=ProviderKey)
        self.provider_key_anthropic.provider_name = "anthropic"
        self.provider_key_anthropic.encrypted_api_key = "encrypted_anthropic_key"
        self.provider_key_anthropic.base_url = None
        self.provider_key_anthropic.model_mapping = "{}"

        self.provider_key_google = MagicMock(spec=ProviderKey)
        self.provider_key_google.provider_name = "gemini"
        self.provider_key_google.encrypted_api_key = "encrypted_gemini_key"
        self.provider_key_google.base_url = None
        self.provider_key_google.model_mapping = json.dumps(
            {"test-gemini": "models/gemini-2.0-flash"}
        )

        self.provider_key_xai = MagicMock(spec=ProviderKey)
        self.provider_key_xai.provider_name = "xai"
        self.provider_key_xai.encrypted_api_key = "encrypted_xai_key"
        self.provider_key_xai.base_url = None
        self.provider_key_xai.model_mapping = json.dumps({"test-xai": "grok-2-1212"})

        self.provider_key_fireworks = MagicMock(spec=ProviderKey)
        self.provider_key_fireworks.provider_name = "fireworks"
        self.provider_key_fireworks.encrypted_api_key = "encrypted_fireworks_key"
        self.provider_key_fireworks.base_url = None
        self.provider_key_fireworks.model_mapping = json.dumps(
            {"test-fireworks": "accounts/fireworks/models/code-llama-7b"}
        )

        self.provider_key_openrouter = MagicMock(spec=ProviderKey)
        self.provider_key_openrouter.provider_name = "openrouter"
        self.provider_key_openrouter.encrypted_api_key = "encrypted_openrouter_key"
        self.provider_key_openrouter.base_url = None
        self.provider_key_openrouter.model_mapping = json.dumps(
            {"test-openrouter": "gpt-4o"}
        )

        self.provider_key_together = MagicMock(spec=ProviderKey)
        self.provider_key_together.provider_name = "together"
        self.provider_key_together.encrypted_api_key = "encrypted_together_key"
        self.provider_key_together.base_url = None
        self.provider_key_together.model_mapping = json.dumps(
            {"test-together": "UAE-Large-V1"}
        )

        self.provider_key_azure = MagicMock(spec=ProviderKey)
        self.provider_key_azure.provider_name = "azure"
        self.provider_key_azure.encrypted_api_key = "encrypted_azure_key"
        self.provider_key_azure.base_url = "https://test-azure.openai.com"
        self.provider_key_azure.model_mapping = json.dumps({"test-azure": "gpt-4o"})

        self.provider_key_bedrock = MagicMock(spec=ProviderKey)
        self.provider_key_bedrock.provider_name = "bedrock"
        self.provider_key_bedrock.encrypted_api_key = "encrypted_bedrock_key"
        self.provider_key_bedrock.base_url = None
        self.provider_key_bedrock.model_mapping = json.dumps({"test-bedrock": "claude-3-5-sonnet-20240620-v1:0"})

        self.user.provider_keys = [
            self.provider_key_openai,
            self.provider_key_anthropic,
            self.provider_key_google,
            self.provider_key_xai,
            self.provider_key_fireworks,
            self.provider_key_openrouter,
            self.provider_key_together,
            self.provider_key_azure,
            self.provider_key_bedrock,
        ]

        # Mock AsyncSession DB
        self.db = AsyncMock()

        # Clear caches
        await async_provider_service_cache.clear()
        await async_user_cache.clear()

        # Create the service with patched decrypt_api_key to avoid actual decryption
        with patch("app.services.provider_service.decrypt_api_key") as mock_decrypt:
            decrypt_key_map = {
                "encrypted_openai_key": "decrypted_openai_key",
                "encrypted_anthropic_key": "decrypted_anthropic_key",
                "encrypted_gemini_key": "decrypted_gemini_key",
                "encrypted_xai_key": "decrypted_xai_key",
                "encrypted_fireworks_key": "decrypted_fireworks_key",
                "encrypted_openrouter_key": "decrypted_openrouter_key",
                "encrypted_together_key": "decrypted_together_key",
                "encrypted_azure_key": json.dumps({
                    "api_key": "decrypted_azure_key",
                    "api_version": "2025-01-01-preview",
                }),
                "encrypted_bedrock_key": json.dumps({
                    "api_key": "decrypted_bedrock_key",
                    "region_name": "us-east-1",
                    "aws_access_key_id": "decrypted_aws_access_key_id",
                    "aws_secret_access_key": "decrypted_aws_secret_access_key",
                }),
            }
            mock_decrypt.side_effect = lambda key: decrypt_key_map[key]

            # Mock user.id for the new constructor signature
            self.user.id = 1

            # Mock the async database execute() pattern for provider keys
            # Create mock result object
            mock_result = MagicMock()  # Result object should be sync, not AsyncMock
            mock_scalars = MagicMock()  # Don't use AsyncMock for scalars object
            mock_scalars.all.return_value = [
                self.provider_key_openai,
                self.provider_key_anthropic,
                self.provider_key_google,
                self.provider_key_xai,
                self.provider_key_fireworks,
                self.provider_key_openrouter,
                self.provider_key_together,
                self.provider_key_azure,
                self.provider_key_bedrock,
            ]
            mock_result.scalars.return_value = mock_scalars  # scalars() returns sync object
            self.db.execute = AsyncMock(return_value=mock_result)  # Only execute() is async

            self.service = ProviderService(self.user.id, self.db)

            # Pre-load the keys for testing
            await self.service._load_provider_keys_async()

    async def test_load_provider_keys(self):
        """Test loading provider keys"""
        # Keys should be loaded in setUp
        keys = self.service.provider_keys

        self.assertIn("openai", keys)
        self.assertIn("anthropic", keys)
        self.assertIn("gemini", keys)
        self.assertIn("xai", keys)
        self.assertIn("fireworks", keys)
        self.assertIn("openrouter", keys)
        self.assertIn("together", keys)
        self.assertIn("azure", keys)
        self.assertIn("bedrock", keys)
        self.assertEqual(keys["openai"]["api_key"], "decrypted_openai_key")
        self.assertEqual(keys["anthropic"]["api_key"], "decrypted_anthropic_key")
        self.assertEqual(keys["gemini"]["api_key"], "decrypted_gemini_key")
        self.assertEqual(keys["xai"]["api_key"], "decrypted_xai_key")
        self.assertEqual(keys["fireworks"]["api_key"], "decrypted_fireworks_key")
        self.assertEqual(keys["openrouter"]["api_key"], "decrypted_openrouter_key")
        self.assertEqual(keys["together"]["api_key"], "decrypted_together_key")
        self.assertEqual(keys["azure"]["api_key"], json.dumps({
            "api_key": "decrypted_azure_key",
            "api_version": "2025-01-01-preview",
        }))
        self.assertEqual(keys["bedrock"]["api_key"], json.dumps({
            "api_key": "decrypted_bedrock_key",
            "region_name": "us-east-1",
            "aws_access_key_id": "decrypted_aws_access_key_id",
            "aws_secret_access_key": "decrypted_aws_secret_access_key",
        }))
        self.assertEqual(keys["openai"]["model_mapping"], {"custom-gpt": "gpt-4"})
        self.assertEqual(
            keys["gemini"]["model_mapping"], {"test-gemini": "models/gemini-2.0-flash"}
        )

    async def test_get_provider_info_explicit_mapping(self):
        """Test getting provider info with an explicitly mapped model"""
        # Since keys are already loaded in setUp, _get_provider_info should work directly
        provider, model, base_url = self.service._get_provider_info("custom-gpt")

        self.assertEqual(provider, "openai")
        self.assertEqual(model, "gpt-4")
        self.assertIsNone(base_url)

        provider, model, base_url = self.service._get_provider_info("test-gemini")

        self.assertEqual(provider, "gemini")
        self.assertEqual(model, "models/gemini-2.0-flash")
        self.assertIsNone(base_url)

    async def test_get_provider_info_prefix_matching(self):
        """Test getting provider info with prefix matching"""
        # Test OpenAI prefix
        provider, model, base_url = self.service._get_provider_info(
            "openai/gpt-3.5-turbo"
        )
        self.assertEqual(provider, "openai")

        # Test Anthropic prefix
        provider, model, base_url = self.service._get_provider_info(
            "anthropic/claude-2"
        )
        self.assertEqual(provider, "anthropic")

        # Test Google prefix
        provider, model, base_url = self.service._get_provider_info(
            "gemini/models/gemini-2.0-flash"
        )
        self.assertEqual(provider, "gemini")

        # Test XAI prefix
        provider, model, base_url = self.service._get_provider_info("xai/grok-2-1212")
        self.assertEqual(provider, "xai")

        # Test Fireworks prefix
        provider, model, base_url = self.service._get_provider_info(
            "fireworks/accounts/fireworks/models/code-llama-7b"
        )
        self.assertEqual(provider, "fireworks")

        # Test OpenRouter prefix
        provider, model, base_url = self.service._get_provider_info(
            "openrouter/openai/gpt-4o"
        )
        self.assertEqual(provider, "openrouter")

        # Test Together prefix
        provider, model, base_url = self.service._get_provider_info(
            "together/WhereIsAI/UAE-Large-V1"
        )
        self.assertEqual(provider, "together")

        provider, model, base_url = self.service._get_provider_info("azure/gpt-4o")
        self.assertEqual(provider, "azure")

        provider, model, base_url = self.service._get_provider_info("bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0")
        self.assertEqual(provider, "bedrock")

    @patch("aiohttp.ClientSession.post")
    async def test_call_openai_api(self, mock_post):
        """Test calling the OpenAI API"""
        # Get the adapter instance
        adapter = ProviderAdapterFactory.get_adapter("openai")

        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200

        # Create a mock coroutine for json() method
        async def mock_json():
            return {"id": "test-id", "object": "chat.completion"}

        mock_response.json = mock_json

        # Set up the mock context managers
        mock_post.return_value.__aenter__.return_value = mock_response

        # Call the method and get the result
        result = await adapter.process_completion(
            "chat/completions", {"model": "gpt-3.5-turbo"}, "test-api-key"
        )

        # Check result
        self.assertEqual(result["id"], "test-id")

        # Verify the API was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-api-key")
        self.assertEqual(kwargs["json"]["model"], "gpt-3.5-turbo")

    @patch("app.services.providers.adapter_factory.ProviderAdapterFactory.get_adapter")
    @patch("app.services.provider_service.decrypt_api_key")
    @patch("app.services.usage_stats_service.UsageStatsService.log_api_request")
    async def test_process_request_routing(self, mock_log_usage, mock_decrypt, mock_get_adapter):
        """Test request routing based on model name"""
        # Create mocks for adapters
        mock_openai_adapter = MagicMock()
        mock_anthropic_adapter = MagicMock()
        mock_gemini_adapter = MagicMock()
        mock_xai_adapter = MagicMock()
        mock_fireworks_adapter = MagicMock()
        mock_openrouter_adapter = MagicMock()
        mock_together_adapter = MagicMock()
        mock_azure_adapter = MagicMock()
        mock_bedrock_adapter = MagicMock()
        # Mock decrypt_api_key to avoid actual decryption
        decrypt_key_map = {
            "encrypted_openai_key": "decrypted_openai_key",
            "encrypted_anthropic_key": "decrypted_anthropic_key",
            "encrypted_gemini_key": "decrypted_gemini_key",
            "encrypted_xai_key": "decrypted_xai_key",
            "encrypted_fireworks_key": "decrypted_fireworks_key",
            "encrypted_openrouter_key": "decrypted_openrouter_key",
            "encrypted_together_key": "decrypted_together_key",
            "encrypted_azure_key": json.dumps({
                "api_key": "decrypted_azure_key",
                "api_version": "2025-01-01-preview",
            }),
            "encrypted_bedrock_key": json.dumps({
                "api_key": "decrypted_bedrock_key",
                "region_name": "us-east-1",
                "aws_access_key_id": "decrypted_aws_access_key_id",
                "aws_secret_access_key": "decrypted_aws_secret_access_key",
            }),
        }
        mock_decrypt.side_effect = lambda key: decrypt_key_map[key]

        # Now we could mock the process_completion method
        mock_openai_adapter.process_completion = AsyncMock(return_value={"id": "openai-response"})

        mock_anthropic_adapter.process_completion = AsyncMock(return_value={"id": "anthropic-response"})

        mock_gemini_adapter.process_completion = AsyncMock(return_value={"id": "gemini-response"})

        mock_xai_adapter.process_completion = AsyncMock(return_value={"id": "xai-response"})

        mock_fireworks_adapter.process_completion = AsyncMock(return_value={"id": "fireworks-response"})

        mock_openrouter_adapter.process_completion = AsyncMock(return_value={"id": "openrouter-response"})

        mock_together_adapter.process_completion = AsyncMock(return_value={"id": "together-response"})

        mock_azure_adapter.process_completion = AsyncMock(return_value={"id": "azure-response"})

        mock_bedrock_adapter.process_completion = AsyncMock(return_value={"id": "bedrock-response"})

        # Configure get_adapter to return the appropriate mock
        provider_mapping = {
            "openai": mock_openai_adapter,
            "anthropic": mock_anthropic_adapter,
            "gemini": mock_gemini_adapter,
            "xai": mock_xai_adapter,
            "fireworks": mock_fireworks_adapter,
            "openrouter": mock_openrouter_adapter,
            "together": mock_together_adapter,
            "azure": mock_azure_adapter,
            "bedrock": mock_bedrock_adapter,
        }
        mock_get_adapter.side_effect = lambda provider, base_url, config: provider_mapping[
            provider
        ]

        # Test OpenAI routing
        result_openai = await self.service.process_request(
            "chat/completions", {"model": "openai/gpt-4"}
        )
        self.assertEqual(result_openai["id"], "openai-response")
        mock_openai_adapter.process_completion.assert_called_once()

        mock_openai_adapter.process_completion.reset_mock()

        # Test Anthropic routing
        result_anthropic = await self.service.process_request(
            "chat/completions", {"model": "anthropic/claude-3-haiku-20240307"}
        )
        self.assertEqual(result_anthropic["id"], "anthropic-response")
        mock_anthropic_adapter.process_completion.assert_called_once()

        mock_anthropic_adapter.process_completion.reset_mock()

        # Test Google routing
        result_gemini = await self.service.process_request(
            "chat/completions", {"model": "gemini/models/gemini-2.0-flash"}
        )
        self.assertEqual(result_gemini["id"], "gemini-response")
        mock_gemini_adapter.process_completion.assert_called_once()

        mock_gemini_adapter.process_completion.reset_mock()

        # Test XAI routing
        result_xai = await self.service.process_request(
            "chat/completions", {"model": "xai/grok-2-1212"}
        )
        self.assertEqual(result_xai["id"], "xai-response")
        mock_xai_adapter.process_completion.assert_called_once()
        mock_xai_adapter.process_completion.reset_mock()

        # Test Fireworks routing
        result_fireworks = await self.service.process_request(
            "chat/completions",
            {"model": "fireworks/accounts/fireworks/models/code-llama-7b"},
        )
        self.assertEqual(result_fireworks["id"], "fireworks-response")
        mock_fireworks_adapter.process_completion.assert_called_once()
        mock_fireworks_adapter.process_completion.reset_mock()

        # Test OpenRouter routing
        result_openrouter = await self.service.process_request(
            "chat/completions", {"model": "openrouter/openai/gpt-4o"}
        )
        self.assertEqual(result_openrouter["id"], "openrouter-response")
        mock_openrouter_adapter.process_completion.assert_called_once()

        mock_openrouter_adapter.process_completion.reset_mock()

        # Test Together routing
        result_together = await self.service.process_request(
            "chat/completions", {"model": "together/WhereIsAI/UAE-Large-V1"}
        )
        self.assertEqual(result_together["id"], "together-response")
        mock_together_adapter.process_completion.assert_called_once()

        mock_together_adapter.process_completion.reset_mock()

        # Test Azure routing
        result_azure = await self.service.process_request(
            "chat/completions", {"model": "azure/gpt-4o"}
        )
        self.assertEqual(result_azure["id"], "azure-response")
        mock_azure_adapter.process_completion.assert_called_once()

        # Test Bedrock routing
        result_bedrock = await self.service.process_request(
            "chat/completions", {"model": "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0"}
        )
        self.assertEqual(result_bedrock["id"], "bedrock-response")
        mock_bedrock_adapter.process_completion.assert_called_once()

        # Test custom model mapping
        mock_openai_adapter.process_completion.reset_mock()
        result_custom = await self.service.process_request(
            "chat/completions", {"model": "custom-gpt"}
        )
        self.assertEqual(result_custom["id"], "openai-response")

        # Verify model was mapped correctly in the call
        args, kwargs = mock_openai_adapter.process_completion.call_args
        # Check the second argument (payload) has the mapped model name
        self.assertEqual(args[1]["model"], "gpt-4")

        # Test another custom model mapping
        mock_openai_adapter.process_completion.reset_mock()
        result_custom = await self.service.process_request(
            "chat/completions", {"model": "test-gemini"}
        )
        self.assertEqual(result_custom["id"], "gemini-response")

        # Verify model was mapped correctly in the call
        args, kwargs = mock_gemini_adapter.process_completion.call_args
        # Check the second argument (payload) has the mapped model name
        self.assertEqual(args[1]["model"], "models/gemini-2.0-flash")
