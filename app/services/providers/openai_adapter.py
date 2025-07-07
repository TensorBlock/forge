from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any

import aiohttp
from app.core.logger import get_logger

from .base import ProviderAdapter

# Configure logging
logger = get_logger(name="openai_adapter")


class OpenAIAdapter(ProviderAdapter):
    """Adapter for OpenAI API"""

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        config: dict[str, Any] | None = None,
    ):
        self._provider_name = provider_name
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @staticmethod
    def get_model_id(payload: dict[str, Any]) -> str:
        """Get the model ID from the payload"""
        if "id" in payload:
            return payload["id"]
        elif "model" in payload:
            return payload["model"]
        elif "model_id" in payload:
            return payload["model_id"]
        else:
            raise ValueError("Model ID not found in payload")

    async def list_models(
        self,
        api_key: str,
        base_url: str | None = None,
        query_params: dict[str, Any] = None,
    ) -> list[str]:
        """List all models (verbosely) supported by the provider"""
        # Check cache first
        base_url = base_url or self._base_url
        cached_models = self.get_cached_models(api_key, base_url)
        if cached_models is not None:
            return cached_models

        # If not in cache, make API call
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{base_url}/models"

        query_params = query_params or {}
        async with (
            aiohttp.ClientSession() as session,
            session.get(url, headers=headers, params=query_params) as response,
        ):
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                raise ValueError(f"{self.provider_name} API error: {error_text}")
            resp = await response.json()

            # Better compatibility with Forge
            models_list = resp["data"] if isinstance(resp, dict) else resp

            self.OPENAI_MODEL_MAPPING = {
                d.get("name", self.get_model_id(d)): self.get_model_id(d) for d in models_list
            }
            models = [self.get_model_id(d) for d in models_list]

            # Cache the results
            self.cache_models(api_key, self._base_url, models)

            return models

    async def process_completion(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
        base_url: str | None = None,
        query_params: dict[str, Any] = None,
    ) -> Any:
        """Process a completion request using OpenAI API"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        url = f"{base_url or self._base_url}/{endpoint}"

        # Check if streaming is requested
        streaming = payload.get("stream", False)

        query_params = query_params or {}
        if streaming:
            # For streaming, return a streaming generator
            async def stream_response() -> AsyncGenerator[bytes, None]:
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(
                        url, headers=headers, json=payload, params=query_params
                    ) as response,
                ):
                    if response.status != HTTPStatus.OK:
                        error_text = await response.text()
                        raise ValueError(
                            f"{self.provider_name} API error: {error_text}"
                        )

                    # Stream the response back
                    async for chunk in response.content:
                        if self.provider_name == "azure":
                            chunk = self.process_streaming_chunk(chunk)
                        logger.info(f"OpenAI streaming chunk: {chunk}")
                        if chunk:
                            yield chunk

            # Return the streaming generator
            return stream_response()
        else:
            # For non-streaming, use the regular approach
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, headers=headers, json=payload, params=query_params
                ) as response,
            ):
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    raise ValueError(f"{self.provider_name} API error: {error_text}")

                return await response.json()

    async def process_image_generation(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> Any:
        """Process an image generation request using OpenAI API"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self._base_url}/{endpoint}"

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, headers=headers, json=payload) as response,
        ):
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                raise ValueError(f"{self.provider_name} API error: {error_text}")

            return await response.json()

    async def process_image_edits(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> Any:
        """Process an image edits request using OpenAI API"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self._base_url}/{endpoint}"

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, headers=headers, json=payload) as response,
        ):
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                raise ValueError(f"{self.provider_name} API error: {error_text}")

            return await response.json()
    
    async def process_embeddings(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
        base_url: str | None = None,
        query_params: dict[str, Any] = None,
    ) -> Any:
        # https://platform.openai.com/docs/api-reference/embeddings/create
        """Process a embeddings request using OpenAI API"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # inpput_type is for cohere embeddings only
        if "input_type" in payload:
            del payload["input_type"]

        url = f"{base_url or self._base_url}/{endpoint}"
        query_params = query_params or {}

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(url, headers=headers, json=payload, params=query_params) as response,
            ):
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    raise ValueError(f"{self.provider_name} API error: {error_text}")

                return await response.json()
        except Exception as e:
            logger.error(f"Error in OpenAI embeddings: {str(e)}", exc_info=True)
            raise
