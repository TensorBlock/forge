import json
import os
from unittest import IsolatedAsyncioTestCase as TestCase
from unittest.mock import patch

from app.services.providers.openai_adapter import OpenAIAdapter
from tests.unit_tests.utils.helpers import (
    ClientSessionMock,
    validate_chat_completion_response,
    OPENAAI_STANDARD_CHAT_COMPLETION_RESPONSE,
    process_openai_streaming_response,
    validate_chat_completion_streaming_response,
)

CURRENT_DIR = os.path.dirname(__file__)

with open(os.path.join(CURRENT_DIR, "docs", "openai", "list_models.json"), "r") as f:
    MOCK_LIST_MODELS_RESPONSE_DATA = json.load(f)

with open(
    os.path.join(CURRENT_DIR, "docs", "openai", "chat_completion_response_1.json"), "r"
) as f:
    MOCK_CHAT_COMPLETION_RESPONSE_DATA = json.load(f)

with open(
    os.path.join(
        CURRENT_DIR, "docs", "openai", "chat_completion_streaming_response_1.json"
    ),
    "r",
) as f:
    MOCK_CHAT_COMPLETION_STREAMING_RESPONSE_DATA = json.load(f)

with open(
    os.path.join(CURRENT_DIR, "docs", "openai", "embeddings_response.json"), "r"
) as f:
    MOCK_EMBEDDINGS_RESPONSE_DATA = json.load(f)


class TestOpenAIProvider(TestCase):
    def setUp(self):
        self.adapter = OpenAIAdapter(
            provider_name="test-openai", base_url="https://api.openai.com/v1"
        )
        self.api_key = "test-api-key"

    async def test_list_models(self):
        # Expected model IDs from the JSON file
        expected_model_ids = [
            "gpt-4-0613",
            "gpt-4",
            "gpt-3.5-turbo",
            "o4-mini-deep-research",
            "o3-deep-research",
            "davinci-002",
            "dall-e-3",
            "dall-e-2",
            "gpt-3.5-turbo-1106",
        ]

        with patch("aiohttp.ClientSession", ClientSessionMock()) as mock_session:
            mock_session.responses = [(MOCK_LIST_MODELS_RESPONSE_DATA, 200)]

            # Call the method
            result = await self.adapter.list_models(api_key=self.api_key)
            # Assert the result contains the expected model IDs
            self.assertEqual(len(result), len(expected_model_ids))
            for model_id in expected_model_ids:
                self.assertIn(model_id, result)

            assert mock_session.get_urls == ["https://api.openai.com/v1/models"]

    async def test_chat_completion(self):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello, how are you?"}],
        }
        with patch("aiohttp.ClientSession", ClientSessionMock()) as mock_session:
            mock_session.responses = [(MOCK_CHAT_COMPLETION_RESPONSE_DATA, 200)]

            # Call the method
            result = await self.adapter.process_completion(
                api_key=self.api_key, payload=payload, endpoint="chat/completions"
            )
            # Assert the result contains the expected model IDs
            validate_chat_completion_response(
                result,
                expected_model="gpt-4o-mini-2024-07-18",
                expected_message=OPENAAI_STANDARD_CHAT_COMPLETION_RESPONSE,
                expected_usage={"prompt_tokens": 13, "completion_tokens": 29},
            )

    async def test_chat_completion_streaming(self):
        payload = {
            "model": "gpt-4o-mini",
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
                api_key=self.api_key, payload=payload, endpoint="chat/completions"
            ):
                if chunk:
                    process_openai_streaming_response(chunk.decode("utf-8"), result)
            # Assert the result contains the expected model IDs
            validate_chat_completion_streaming_response(
                result,
                expected_model="gpt-4o-mini-2024-07-18",
                expected_message=OPENAAI_STANDARD_CHAT_COMPLETION_RESPONSE,
            )

    async def test_process_embeddings(self):
        payload = {
            "model": "text-embedding-ada-002",
            "input": ["hello", "world"],
        }
        with patch("aiohttp.ClientSession", ClientSessionMock()) as mock_session:
            mock_session.responses = [(MOCK_EMBEDDINGS_RESPONSE_DATA, 200)]

            # Call the method
            result = await self.adapter.process_embeddings(
                api_key=self.api_key, payload=payload, endpoint="embeddings"
            )
            self.assertEqual(result, MOCK_EMBEDDINGS_RESPONSE_DATA)

            # verify that the payload sent to openai has a list as input
            self.assertIsInstance(mock_session.posted_json[0]["input"], list)
