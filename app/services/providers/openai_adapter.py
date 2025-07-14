from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any

import aiohttp
from app.core.logger import get_logger
from app.exceptions.exceptions import ProviderAPIException, BaseInvalidRequestException

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

    def validate_messages(self, messages: list[dict[str, Any]]) -> None:
        """Validate message structure for OpenAI API compatibility"""
        if not messages:
            return
            
        for i, message in enumerate(messages):
            role = message.get("role")
            
            # Check for tool messages that don't have proper preceding tool_calls
            if role == "tool":
                # Find the preceding assistant message with tool_calls
                has_preceding_tool_calls = False
                for j in range(i - 1, -1, -1):
                    prev_message = messages[j]
                    if prev_message.get("role") == "assistant":
                        if "tool_calls" in prev_message:
                            has_preceding_tool_calls = True
                            break
                        elif "content" in prev_message:
                            # If assistant message has content but no tool_calls, 
                            # it's not a valid preceding message for tool role
                            break
                
                if not has_preceding_tool_calls:
                    error_msg = f"Message at index {i} with role 'tool' must be a response to a preceding message with 'tool_calls'"
                    logger.error(f"OpenAI API validation error: {error_msg}")
                    raise BaseInvalidRequestException(
                        provider_name=self.provider_name,
                        error=ValueError(error_msg)
                    )

    def validate_tools(self, tools: list[dict[str, Any]]) -> None:
        """Validate tools structure for OpenAI API compatibility"""
        if not tools:
            return
            
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                error_msg = f"Tool at index {i} must be a dictionary"
                logger.error(f"OpenAI API validation error: {error_msg}")
                raise BaseInvalidRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_msg)
                )
            
            tool_type = tool.get("type")
            if tool_type != "function":
                error_msg = f"Tool at index {i} has unsupported type '{tool_type}'. Only 'function' type is supported"
                logger.error(f"OpenAI API validation error: {error_msg}")
                raise BaseInvalidRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_msg)
                )
            
            function = tool.get("function")
            if not function or not isinstance(function, dict):
                error_msg = f"Tool at index {i} must have a 'function' object"
                logger.error(f"OpenAI API validation error: {error_msg}")
                raise BaseInvalidRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_msg)
                )
            
            function_name = function.get("name")
            if not function_name or not isinstance(function_name, str):
                error_msg = f"Function at index {i} must have a valid 'name' string"
                logger.error(f"OpenAI API validation error: {error_msg}")
                raise BaseInvalidRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_msg)
                )

    def validate_tool_choice(self, tool_choice: Any) -> None:
        """Validate tool_choice parameter for OpenAI API compatibility"""
        if tool_choice is None:
            return
            
        if isinstance(tool_choice, str):
            valid_choices = ["none", "auto"]
            if tool_choice not in valid_choices:
                error_msg = f"tool_choice must be one of {valid_choices}, got '{tool_choice}'"
                logger.error(f"OpenAI API validation error: {error_msg}")
                raise BaseInvalidRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_msg)
                )
        elif isinstance(tool_choice, dict):
            if "type" not in tool_choice:
                error_msg = "tool_choice object must have a 'type' field"
                logger.error(f"OpenAI API validation error: {error_msg}")
                raise BaseInvalidRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_msg)
                )
            
            tool_choice_type = tool_choice.get("type")
            if tool_choice_type == "function":
                if "function" not in tool_choice:
                    error_msg = "tool_choice with type 'function' must have a 'function' object"
                    logger.error(f"OpenAI API validation error: {error_msg}")
                    raise BaseInvalidRequestException(
                        provider_name=self.provider_name,
                        error=ValueError(error_msg)
                    )
            elif tool_choice_type not in ["none", "auto"]:
                error_msg = f"tool_choice type must be one of ['none', 'auto', 'function'], got '{tool_choice_type}'"
                logger.error(f"OpenAI API validation error: {error_msg}")
                raise BaseInvalidRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_msg)
                )
        else:
            error_msg = f"tool_choice must be a string or object, got {type(tool_choice).__name__}"
            logger.error(f"OpenAI API validation error: {error_msg}")
            raise BaseInvalidRequestException(
                provider_name=self.provider_name,
                error=ValueError(error_msg)
            )

    def get_model_id(self, payload: dict[str, Any]) -> str:
        """Get the model ID from the payload"""
        if "id" in payload:
            return payload["id"]
        elif "model" in payload:
            return payload["model"]
        elif "model_id" in payload:
            return payload["model_id"]
        else:
            logger.error(f"Model ID not found in payload for {self.provider_name}")
            raise BaseInvalidRequestException(
                provider_name=self.provider_name,
                error=ValueError("Model ID not found in payload")
            )

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
                logger.error(f"List Models API error for {self.provider_name}: {error_text}")
                raise ProviderAPIException(
                    provider_name=self.provider_name,
                    error_code=response.status,
                    error_message=error_text
                )
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
        # Validate messages before sending to API
        if "messages" in payload:
            self.validate_messages(payload["messages"])
        
        # Validate tools if present
        if "tools" in payload:
            self.validate_tools(payload["tools"])
        
        # Validate tool_choice if present
        if "tool_choice" in payload:
            self.validate_tool_choice(payload["tool_choice"])
            
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
                        logger.error(f"Completion Streaming API error for {self.provider_name}: {error_text}")
                        raise ProviderAPIException(
                            provider_name=self.provider_name,
                            error_code=response.status,
                            error_message=error_text
                        )

                    # Stream the response back
                    async for chunk in response.content:
                        if self.provider_name == "azure":
                            chunk = self.process_streaming_chunk(chunk)
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
                    logger.error(f"Completion API error for {self.provider_name}: {error_text}")
                    raise ProviderAPIException(
                        provider_name=self.provider_name,
                        error_code=response.status,
                        error_message=error_text
                    )

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
                logger.error(f"Image Generation API error for {self.provider_name}: {error_text}")
                raise ProviderAPIException(
                    provider_name=self.provider_name,
                    error_code=response.status,
                    error_message=error_text
                )

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
                logger.error(f"API error for {self.provider_name}: {error_text}")
                raise ProviderAPIException(
                    provider_name=self.provider_name,
                    error_code=response.status,
                    error_message=error_text
                )

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

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, headers=headers, json=payload, params=query_params) as response,
        ):
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                logger.error(f"Embeddings API error for {self.provider_name}: {error_text}")
                raise ProviderAPIException(
                    provider_name=self.provider_name,
                    error_code=response.status,
                    error_message=error_text
                )

            return await response.json()
