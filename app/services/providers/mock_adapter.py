"""
Mock provider adapter for testing purposes.
"""

from collections.abc import AsyncGenerator
from typing import Any

from .base import ProviderAdapter
from .mock_provider import (
    generate_mock_chat_stream,
    get_mock_chat_completion,
    get_mock_models,
    get_mock_text_completion,
)


class MockAdapter(ProviderAdapter):
    """Adapter for the Mock provider"""

    def __init__(self, provider_name: str, base_url: str | None = None):
        self._provider_name = provider_name
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        """Return the provider name"""
        return self._provider_name

    @property
    def model_mapping(self) -> dict[str, str]:
        """Return the model mapping"""
        return {
            "mock-only-gpt-3.5-turbo": "mock-gpt-3.5-turbo",
            "mock-only-gpt-4": "mock-gpt-4",
            "mock-only-gpt-4o": "mock-gpt-4o",
            "mock-only-claude-3-opus": "mock-claude-3-opus",
            "mock-only-claude-3-sonnet": "mock-claude-3-sonnet",
            "mock-only-claude-3-haiku": "mock-claude-3-haiku",
        }

    async def process_completion(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
        base_url: str | None = None,
    ) -> Any:
        """Process a completion request"""
        model = payload.get("model", "mock-gpt-3.5-turbo")

        if endpoint == "chat/completions":
            messages = payload.get("messages", [])
            temperature = payload.get("temperature", 0.7)
            stream = payload.get("stream", False)
            max_tokens = payload.get("max_tokens")

            if stream:
                # For streaming, return a generator
                return generate_mock_chat_stream(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                # For regular chat completion
                return get_mock_chat_completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    stream=stream,
                    max_tokens=max_tokens,
                )

        elif endpoint == "completions":
            prompt = payload.get("prompt", "")
            temperature = payload.get("temperature", 0.7)
            stream = payload.get("stream", False)
            max_tokens = payload.get("max_tokens")

            return get_mock_text_completion(
                model=model,
                prompt=prompt,
                temperature=temperature,
                stream=stream,
                max_tokens=max_tokens,
            )

        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}")

    def get_mapped_model(self, model: str) -> str:
        """Get the provider-specific model name for the given model"""
        if model.startswith("mock-"):
            return model
        return self.model_mapping.get(model, model)

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        stream: bool = False,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict:
        """Make a chat completion request to the mock provider"""
        return get_mock_chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=stream,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def text_completion(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        stream: bool = False,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict:
        """Make a text completion request to the mock provider"""
        return get_mock_text_completion(
            model=model,
            prompt=prompt,
            temperature=temperature,
            stream=stream,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def list_models(self, api_key: str, base_url: str | None = None) -> list[str]:
        """List available models from the mock provider"""
        # Return the full list of mock model IDs
        mock_models = get_mock_models()
        mock_model_ids = [m["id"] for m in mock_models]

        # Add the keys from the model mapping (mock-only-* prefixed models)
        # instead of the values (which are the mock-* implementation names)
        mapped_models = list(self.model_mapping.keys())

        # Return both types of mock models
        all_models = list(set(mock_model_ids + mapped_models))

        return all_models

    async def stream_chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat completion from the mock provider"""
        async for chunk in generate_mock_chat_stream(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            if chunk == "[DONE]":
                return
            yield {"chunk": chunk}
