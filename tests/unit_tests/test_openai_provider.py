import json
import os
from unittest import IsolatedAsyncioTestCase as TestCase
from unittest.mock import patch
import pytest

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

    def test_openai_adapter_tool_message_validation(self):
        """Test that OpenAI adapter validates tool messages correctly"""
        from app.services.providers.openai_adapter import OpenAIAdapter
        from app.exceptions.exceptions import BaseInvalidRequestException
        
        adapter = OpenAIAdapter("openai", "https://api.openai.com/v1")
        
        # Test valid tool message sequence
        valid_messages = [
            {"role": "user", "content": "What's the weather like?"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}]},
            {"role": "tool", "content": "Sunny", "tool_call_id": "call_1"}
        ]
        
        # This should not raise an exception
        adapter.validate_messages(valid_messages)
        
        # Test invalid tool message sequence (no preceding tool_calls)
        invalid_messages = [
            {"role": "user", "content": "What's the weather like?"},
            {"role": "assistant", "content": "I'll check the weather for you."},
            {"role": "tool", "content": "Sunny", "tool_call_id": "call_1"}  # This should fail
        ]
        
        # This should raise an exception
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_messages(invalid_messages)
        
        assert "tool' must be a response to a preceding message with 'tool_calls'" in str(exc_info.value)
        
        # Test tool message with assistant message that has content but no tool_calls
        invalid_messages_2 = [
            {"role": "user", "content": "What's the weather like?"},
            {"role": "assistant", "content": "Let me check that for you."},
            {"role": "tool", "content": "Sunny", "tool_call_id": "call_1"}  # This should fail
        ]
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_messages(invalid_messages_2)
        
        assert "tool' must be a response to a preceding message with 'tool_calls'" in str(exc_info.value)

    def test_openai_adapter_tools_validation(self):
        """Test that OpenAI adapter validates tools correctly"""
        from app.services.providers.openai_adapter import OpenAIAdapter
        from app.exceptions.exceptions import BaseInvalidRequestException
        
        adapter = OpenAIAdapter("openai", "https://api.openai.com/v1")
        
        # Test valid tools
        valid_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "The city and state"}
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        
        # This should not raise an exception
        adapter.validate_tools(valid_tools)
        
        # Test invalid tool (wrong type)
        invalid_tools_1 = [
            {
                "type": "retrieval",  # Wrong type
                "function": {
                    "name": "get_weather",
                    "description": "Get the weather"
                }
            }
        ]
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tools(invalid_tools_1)
        
        assert "unsupported type 'retrieval'. Only 'function' type is supported" in str(exc_info.value)
        
        # Test invalid tool (missing function)
        invalid_tools_2 = [
            {
                "type": "function"
                # Missing function object
            }
        ]
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tools(invalid_tools_2)
        
        assert "must have a 'function' object" in str(exc_info.value)
        
        # Test invalid tool (missing function name)
        invalid_tools_3 = [
            {
                "type": "function",
                "function": {
                    "description": "Get the weather"
                    # Missing name
                }
            }
        ]
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tools(invalid_tools_3)
        
        assert "must have a valid 'name' string" in str(exc_info.value)
        
        # Test empty tools list
        adapter.validate_tools([])

    def test_openai_adapter_tool_choice_validation(self):
        """Test that OpenAI adapter validates tool_choice correctly"""
        from app.services.providers.openai_adapter import OpenAIAdapter
        from app.exceptions.exceptions import BaseInvalidRequestException
        
        adapter = OpenAIAdapter("openai", "https://api.openai.com/v1")
        
        # Test valid string tool_choice values
        valid_choices = ["none", "auto"]
        for choice in valid_choices:
            adapter.validate_tool_choice(choice)
        
        # Test valid object tool_choice
        valid_object_choice = {
            "type": "function",
            "function": {"name": "get_weather"}
        }
        adapter.validate_tool_choice(valid_object_choice)
        
        # Test invalid string tool_choice
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tool_choice("invalid")
        
        assert "tool_choice must be one of ['none', 'auto'], got 'invalid'" in str(exc_info.value)
        
        # Test invalid object tool_choice (missing type)
        invalid_object_choice_1 = {
            "function": {"name": "get_weather"}
            # Missing type
        }
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tool_choice(invalid_object_choice_1)
        
        assert "must have a 'type' field" in str(exc_info.value)
        
        # Test invalid object tool_choice (function type without function)
        invalid_object_choice_2 = {
            "type": "function"
            # Missing function object
        }
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tool_choice(invalid_object_choice_2)
        
        assert "must have a 'function' object" in str(exc_info.value)
        
        # Test invalid object tool_choice (invalid type)
        invalid_object_choice_3 = {
            "type": "invalid_type"
        }
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tool_choice(invalid_object_choice_3)
        
        assert "type must be one of ['none', 'auto', 'function'], got 'invalid_type'" in str(exc_info.value)
        
        # Test None tool_choice
        adapter.validate_tool_choice(None)


    def test_anthropic_adapter_function_calling_validation(self):
        """Test that Anthropic adapter validates function calling correctly"""
        from app.services.providers.anthropic_adapter import AnthropicAdapter
        from app.exceptions.exceptions import BaseInvalidRequestException
        
        adapter = AnthropicAdapter("anthropic", "https://api.anthropic.com", {})
        
        # Test valid tools
        valid_tools = [
            {
                "function": {
                    "name": "get_weather",
                    "description": "Get the weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "The city and state"}
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        
        # This should not raise an exception
        adapter.validate_tools(valid_tools)
        
        # Test invalid tool (missing function)
        invalid_tools_1 = [
            {
                "type": "function"
                # Missing function object
            }
        ]
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tools(invalid_tools_1)
        
        assert "must have a 'function' object" in str(exc_info.value)
        
        # Test invalid tool (missing function name)
        invalid_tools_2 = [
            {
                "function": {
                    "description": "Get the weather"
                    # Missing name
                }
            }
        ]
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_tools(invalid_tools_2)
        
        assert "must have a valid 'name' string" in str(exc_info.value)
        
        # Test valid tool message sequence
        valid_messages = [
            {"role": "user", "content": "What's the weather like?"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}]},
            {"role": "tool", "content": "Sunny", "tool_call_id": "call_1"}
        ]
        
        # This should not raise an exception
        adapter.validate_messages(valid_messages)
        
        # Test invalid tool message sequence (no preceding tool_calls)
        invalid_messages = [
            {"role": "user", "content": "What's the weather like?"},
            {"role": "assistant", "content": "I'll check the weather for you."},
            {"role": "tool", "content": "Sunny", "tool_call_id": "call_1"}  # This should fail
        ]
        
        with pytest.raises(BaseInvalidRequestException) as exc_info:
            adapter.validate_messages(invalid_messages)
        
        assert "tool' must be a response to a preceding message with 'tool_calls'" in str(exc_info.value)
