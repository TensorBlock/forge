import json
import os
from unittest import IsolatedAsyncioTestCase as TestCase
from unittest.mock import patch

from app.services.providers.google_adapter import GoogleAdapter
from tests.unit_tests.utils.helpers import (
    ClientSessionMock,
    validate_chat_completion_response,
    GOOGLE_STANDARD_CHAT_COMPLETION_RESPONSE,
    process_openai_streaming_response,
    validate_chat_completion_streaming_response,
)

CURRENT_DIR = os.path.dirname(__file__)

with open(os.path.join(CURRENT_DIR, "assets", "google", "list_models.json"), "r") as f:
    MOCK_LIST_MODELS_RESPONSE_DATA = json.load(f)

with open(
    os.path.join(CURRENT_DIR, "assets", "google", "chat_completion_response_1.json"), "r"
) as f:
    MOCK_CHAT_COMPLETION_RESPONSE_DATA = json.load(f)

with open(
    os.path.join(
        CURRENT_DIR, "assets", "google", "chat_completion_streaming_response_1.json"
    ),
    "r",
) as f:
    MOCK_CHAT_COMPLETION_STREAMING_RESPONSE_DATA = json.load(f)


class TestGoogleProvider(TestCase):
    def setUp(self):
        self.adapter = GoogleAdapter(
            provider_name="test-google",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            config=None,
        )
        self.api_key = "test-api-key"

    async def test_list_models(self):
        # Expected model IDs from the JSON file
        expected_model_ids = [
            "models/embedding-gecko-001",
            "models/gemini-1.0-pro-vision-latest",
            "models/gemini-pro-vision",
            "models/gemini-1.5-pro-latest",
            "models/gemini-1.5-pro-002",
        ]

        with patch("aiohttp.ClientSession", ClientSessionMock()) as mock_session:
            mock_session.responses = [(MOCK_LIST_MODELS_RESPONSE_DATA, 200)]

            # Call the method
            result = await self.adapter.list_models(api_key=self.api_key)
            # Assert the result contains the expected model IDs
            self.assertEqual(len(result), len(expected_model_ids))
            for model_id in expected_model_ids:
                self.assertIn(model_id, result)

            assert mock_session.get_urls == [
                "https://generativelanguage.googleapis.com/v1beta/models"
            ]

    async def test_chat_completion(self):
        payload = {
            "model": "models/gemini-1.5-pro-latest",
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
                expected_model="models/gemini-1.5-pro-latest",
                expected_message=GOOGLE_STANDARD_CHAT_COMPLETION_RESPONSE,
                expected_usage={"prompt_tokens": 6, "completion_tokens": 16},
            )
            assert mock_session.posted_json[0] == {
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                    "stopSequences": [],
                },
                "contents": [
                    {
                        "parts": [{"text": "Hello, how are you?"}],
                        "role": "user",
                    }
                ],
            }

    async def test_chat_completion_streaming(self):
        payload = {
            "model": "models/gemini-1.5-pro-latest",
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
                expected_model="models/gemini-1.5-pro-latest",
                expected_message=GOOGLE_STANDARD_CHAT_COMPLETION_RESPONSE,
                expected_usage={"prompt_tokens": 6, "completion_tokens": 16},
            )
            assert mock_session.posted_json[0] == {
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                    "stopSequences": [],
                },
                "contents": [
                    {
                        "parts": [{"text": "Hello, how are you?"}],
                        "role": "user",
                    }
                ],
            }
