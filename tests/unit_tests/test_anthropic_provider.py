import json
import os
from unittest import IsolatedAsyncioTestCase as TestCase
from unittest.mock import patch

from app.services.providers.anthropic_adapter import AnthropicAdapter
from tests.unit_tests.utils.helpers import (
    ClientSessionMock,
    validate_chat_completion_response,
    ANTHROPIC_STANDARD_CHAT_COMPLETION_RESPONSE,
    process_openai_streaming_response,
    validate_chat_completion_streaming_response,
)

CURRENT_DIR = os.path.dirname(__file__)

with open(os.path.join(CURRENT_DIR, "docs", "anthropic", "list_models.json"), "r") as f:
    MOCK_LIST_MODELS_RESPONSE_DATA = json.load(f)

with open(
    os.path.join(CURRENT_DIR, "docs", "anthropic", "chat_completion_response_1.json"),
    "r",
) as f:
    MOCK_CHAT_COMPLETION_RESPONSE_DATA = json.load(f)

with open(
    os.path.join(
        CURRENT_DIR, "docs", "anthropic", "chat_completion_streaming_response_1.json"
    ),
    "r",
) as f:
    MOCK_CHAT_COMPLETION_STREAMING_RESPONSE_DATA = json.load(f)


class TestAnthropicProvider(TestCase):
    def setUp(self):
        self.adapter = AnthropicAdapter(
            provider_name="test-anthropic",
            base_url="https://api.anthropic.com/v1",
            config=None,
        )
        self.api_key = "test-api-key"

    async def test_list_models(self):
        expected_model_ids = [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
        ]
        with patch("aiohttp.ClientSession", ClientSessionMock()) as mock_session:
            mock_session.responses = [(MOCK_LIST_MODELS_RESPONSE_DATA, 200)]

            # Call the method
            result = await self.adapter.list_models(api_key=self.api_key)
            # Assert the result contains the expected model IDs
            self.assertEqual(len(result), len(expected_model_ids))

    async def test_chat_completion(self):
        payload = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello, how are you?"}],
        }
        with patch("aiohttp.ClientSession", ClientSessionMock()) as mock_session:
            mock_session.responses = [(MOCK_CHAT_COMPLETION_RESPONSE_DATA, 200)]

            # Call the method
            result = await self.adapter.process_completion(
                api_key=self.api_key, payload=payload, endpoint="messages"
            )
            # Assert the result contains the expected model IDs
            validate_chat_completion_response(
                result,
                expected_model="claude-sonnet-4-20250514",
                expected_message=ANTHROPIC_STANDARD_CHAT_COMPLETION_RESPONSE,
                expected_usage={"prompt_tokens": 13, "completion_tokens": 39},
            )
            assert mock_session.posted_json[0] == {
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
                "max_tokens": 4096,
                "temperature": 1.0,
                "stop_sequences": [],
            }

    async def test_chat_completion_streaming(self):
        payload = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello, how are you?"}],
            "stream": True,
        }
        with patch("aiohttp.ClientSession", ClientSessionMock()) as mock_session:
            mock_session.responses = [
                (MOCK_CHAT_COMPLETION_STREAMING_RESPONSE_DATA, 200)
            ]

            # Call the method
            result = {}
            async for chunk in await self.adapter.process_completion(
                api_key=self.api_key, payload=payload, endpoint="messages"
            ):
                if chunk:
                    process_openai_streaming_response(chunk.decode("utf-8"), result)
            # Assert the result contains the expected model IDs
            validate_chat_completion_streaming_response(
                result,
                expected_model="claude-sonnet-4-20250514",
                expected_message=ANTHROPIC_STANDARD_CHAT_COMPLETION_RESPONSE,
                expected_usage={"prompt_tokens": 13, "completion_tokens": 39},
            )
            assert mock_session.posted_json[0] == {
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
                "max_tokens": 4096,
                "temperature": 1.0,
                "stop_sequences": [],
                "stream": True,
            }
