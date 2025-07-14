import json
import time
import uuid
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any

import aiohttp

from app.core.logger import get_logger
from app.exceptions.exceptions import ProviderAPIException, BaseForgeException

from .base import ProviderAdapter

# Configure logging
logger = get_logger(name="cohere_adapter")


class CohereAdapter(ProviderAdapter):
    def __init__(self, provider_name: str, base_url: str | None = None, config: dict[str, str] | None = None):
        self._provider_name = provider_name
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def get_mapped_model(self, model: str) -> str:
        return model

    async def list_models(self, api_key: str) -> list[str]:
        """List all models (verbosely) supported by the provider"""
        # Cohere still uses v1 api to list models
        base_url = f"{self._base_url}/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        params = {
            "page_size": 1000,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                base_url, headers=headers, params=params
            ) as response:
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    logger.error(f"List models API error for {self.provider_name}: {error_text}")
                    raise ProviderAPIException(
                        provider_name=self.provider_name,
                        error_code=response.status,
                        error_message=error_text
                    )
                resp = await response.json()
                models = [d["name"] for d in resp["models"]]

                # Cache the results
                self.cache_models(api_key, base_url, models)

                return models

    @staticmethod
    def convert_usage_data(usage_metadata: dict[str, Any]) -> dict[str, Any]:
        """Convert Cohere usage data to OpenAI format"""
        # cohere only billed a specific amount of tokens
        usage_metadata = usage_metadata or {}
        billed_tokens = usage_metadata.get("billed_units", {})
        prompt_tokens = billed_tokens.get("input_tokens", 0)
        completion_tokens = billed_tokens.get("output_tokens", 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    def _convert_cohere_to_openai(
        self, cohere_response: dict[str, Any], model: str
    ) -> dict[str, Any]:
        """Convert Cohere response format to OpenAI format"""
        openai_response = {
            "id": cohere_response["id"],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        # Extract the candidates
        message = cohere_response.get("message")
        if not message:
            logger.warning("No message in Cohere response")
            openai_response["choices"] = [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "error",
                }
            ]
            return openai_response

        content = message["content"]
        text_content = "".join([c["text"] for c in content])
        openai_response["choices"] = [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text_content},
                "finish_reason": cohere_response.get("finish_reason", "stop"),
            }
        ]

        # Set usage estimates if available
        usage_metadata = cohere_response.get("usage", {})
        if usage_metadata:
            openai_response["usage"] = self.convert_usage_data(usage_metadata)

        return openai_response

    async def _stream_cohere_response(
        self, api_key: str, payload: dict[str, Any]
    ) -> AsyncGenerator[bytes, None]:
        """Stream a completion request using Cohere API"""
        model = payload["model"]
        try:
            url = f"{self._base_url}/v2/chat"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(url, json=payload, headers=headers) as response,
            ):
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    logger.error(f"Streaming completion API error for {self.provider_name}: {error_text}")
                    raise ProviderAPIException(
                        provider_name=self.provider_name,
                        error_code=response.status,
                        error_message=error_text
                    )

                # Track the message ID for consistency
                message_id = None
                created = int(time.time())
                final_usage_data = None
                async for chunk in response.content.iter_chunks():
                    if not chunk[0]:  # Skip empty chunks
                        continue

                    try:
                        # Parse SSE format
                        chunk_text = chunk[0].decode("utf-8")
                        if not chunk_text.strip():
                            continue

                        # Split into individual SSE events (separated by double newlines)
                        events = chunk_text.strip().split("\n\n")
                        for event_text in events:
                            if not event_text.strip():
                                continue

                            # Skip [DONE] event
                            if event_text.strip() == "data: [DONE]":
                                continue

                            # Split into lines and process SSE format
                            lines = event_text.split("\n")
                            # event_type = None
                            data = None

                            for line in lines:
                                # if line.startswith("event: "):
                                # event_type = line[7:].strip()
                                if line.startswith("data: "):
                                    data = line[6:].strip()

                            if not data:
                                continue

                            cohere_chunk = json.loads(data)
                            chunk_type = cohere_chunk.get("type")

                            # Initialize message ID on first chunk
                            if message_id is None:
                                message_id = cohere_chunk.get(
                                    "id", f"chatcmpl-{uuid.uuid4()}"
                                )

                            openai_chunk = None
                            # Convert to OpenAI format based on chunk type
                            if chunk_type == "message-start":
                                openai_chunk = {
                                    "id": message_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "role": "assistant",
                                                "content": "",
                                            },
                                            "finish_reason": None,
                                        }
                                    ],
                                }

                            elif chunk_type == "content-delta":
                                content = (
                                    cohere_chunk.get("delta", {})
                                    .get("message", {})
                                    .get("content", {})
                                    .get("text", "")
                                )
                                openai_chunk = {
                                    "id": message_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": content},
                                            "finish_reason": None,
                                        }
                                    ],
                                }

                            elif chunk_type in ["content-end", "content-start"]:
                                # For content-end/content-start, we send an empty content delta
                                openai_chunk = {
                                    "id": message_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": ""},
                                            "finish_reason": None,
                                        }
                                    ],
                                }

                            elif chunk_type == "message-end":
                                finish_reason = cohere_chunk.get("delta", {}).get(
                                    "finish_reason", "stop"
                                )
                                usage_metadata = cohere_chunk.get("usage", {})
                                if usage_metadata:
                                    final_usage_data = self.convert_usage_data(
                                        usage_metadata
                                    )

                                openai_chunk = {
                                    "id": message_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {},
                                            "finish_reason": finish_reason,
                                        }
                                    ],
                                }

                            if openai_chunk:
                                yield f"data: {json.dumps(openai_chunk)}\n\n".encode()
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse Cohere chunk: {chunk[0]}")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing Cohere chunk: {e}")
                        continue
                if final_usage_data:
                    usage_chunk = {
                        "id": message_id or uuid.uuid4(),
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [],
                        "usage": final_usage_data,
                    }
                    yield f"data: {json.dumps(usage_chunk)}\n\n".encode()

                # # Send final [DONE] message
                yield b"data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Streaming completion API error for {self.provider_name}: {e}", exc_info=True)
            error_chunk = {
                "id": uuid.uuid4(),
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "error"}],
                "error": {"message": str(e), "type": "api_error"},
            }
            yield f"data: {json.dumps(error_chunk)}\n\n".encode()
            yield b"data: [DONE]\n\n"

    async def _process_cohere_chat_completion(
        self, api_key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a chat completion request using Cohere API"""
        url = f"{self._base_url}/v2/chat"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    logger.error(f"Completion API error for {self.provider_name}: {error_text}")
                    raise ProviderAPIException(
                        provider_name=self.provider_name,
                        error_code=response.status,
                        error_message=error_text
                    )
                resp = await response.json()
                return self._convert_cohere_to_openai(resp, payload["model"])

    async def process_completion(
        self, endpoint: str, payload: dict[str, Any], api_key: str
    ) -> Any:
        """Process a completion request using Cohere API"""
        if endpoint != "chat/completions":
            raise NotImplementedError(
                f"Cohere adapter doesn't support endpoint {endpoint}"
            )

        # For chat completions, delegate to appropriate method
        is_streaming = payload.get("stream", False)
        if is_streaming:
            return self._stream_cohere_response(api_key, payload)
        else:
            return await self._process_cohere_chat_completion(api_key, payload)
    
    @staticmethod
    def convert_openai_embeddings_payload_to_cohere(payload: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI embeddings payload to Cohere format"""
        cohere_payload = {
            "model": payload["model"],
            "input_type": payload.get("input_type", "search_document"),
            # The only supported embedding type is float
            "embedding_types": ["float"],
        }
        input = payload['input']
        if isinstance(input, str):
            cohere_payload["texts"] = [input]
        elif isinstance(input, list):
            cohere_payload["texts"] = input
        
        return cohere_payload
    
    @staticmethod
    def convert_cohere_embeddings_response_to_openai(response_json: dict[str, Any], model: str) -> dict[str, Any]:
        """Convert Cohere embeddings response to OpenAI format"""
        openai_response = {
            "object": "list",
            "data": [],
            "model": model,
            "usage": {
                "prompt_tokens": 0,
                "total_tokens": 0,
            },
        }
        embeddings = response_json["embeddings"]
        values = embeddings.get("float", embeddings.get("binary", []))
        for idx, v in enumerate(values):
            openai_response["data"].append({
                "object": "embedding",
                "embedding": v,
                "index": idx,
            })
        billed_units = response_json.get("meta", {}).get("billed_units")
        if billed_units:
            usage = openai_response["usage"]
            usage["prompt_tokens"] = billed_units.get("input_tokens", 0)
            usage["total_tokens"] = billed_units.get("output_tokens", billed_units.get("input_tokens", 0))
        return openai_response
    
    async def process_embeddings(
        self, endpoint: str, payload: dict[str, Any], api_key: str
    ) -> Any:
        """Process a embeddings request using Cohere API"""
        # https://docs.cohere.com/v2/reference/embed
        url = f"{self._base_url}/v2/embed"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        cohere_payload = self.convert_openai_embeddings_payload_to_cohere(payload)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=cohere_payload) as response:
                    if response.status != HTTPStatus.OK:
                        error_text = await response.text()
                        logger.error(f"Embeddings API error for {self.provider_name}: {error_text}")
                        raise ProviderAPIException(
                            provider_name=self.provider_name,
                            error_code=response.status,
                            error_message=error_text
                        )
                    response_json = await response.json()
                    return self.convert_cohere_embeddings_response_to_openai(response_json, payload["model"])
        except BaseForgeException as e:
            raise e
        except Exception as e:
            error_text = f"Embeddings API error for {self.provider_name}: {e}"
            logger.error(error_text, exc_info=True)
            raise ProviderAPIException(
                provider_name=self.provider_name,
                error_code=500,
                error_message=error_text
            )
                
