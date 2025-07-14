import json
import time
import uuid
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any

import aiohttp

from app.core.logger import get_logger
from app.exceptions.exceptions import ProviderAPIException, InvalidCompletionRequestException

from .base import ProviderAdapter

logger = get_logger(name="anthropic_adapter")

ANTHROPIC_DEFAULT_MAX_TOKENS = 4096


class AnthropicAdapter(ProviderAdapter):
    """Adapter for Anthropic API"""

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        config: dict[str, Any],
    ):
        self._provider_name = provider_name
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @staticmethod
    def convert_openai_image_content_to_anthropic(
        msg: dict[str, Any],
    ) -> dict[str, Any]:
        """Convert OpenAI image content to Anthropic image content"""
        data_url = msg["image_url"]["url"]
        if data_url.startswith("data:"):
            # Extract media type and base64 data
            parts = data_url.split(",", 1)
            media_type = parts[0].split(":")[1].split(";")[0]  # e.g., "image/jpeg"
            base64_data = parts[1]  # The actual base64 string without prefix
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_data,
                },
            }
        else:
            return {"type": "image", "source": {"type": "url", "url": data_url}}

    @staticmethod
    def convert_openai_content_to_anthropic(
        content: list[dict[str, Any]] | str,
    ) -> list[dict[str, Any]]:
        """Convert OpenAI content model to Anthropic content model"""
        if isinstance(content, str):
            return content

        result = []
        for msg in content:
            _type = msg["type"]
            if _type == "text":
                result.append({"type": "text", "text": msg["text"]})
            elif _type == "image_url":
                result.append(
                    AnthropicAdapter.convert_openai_image_content_to_anthropic(msg)
                )
            else:
                error_message = f"{_type} is not supported"
                logger.error(error_message)
                raise InvalidCompletionRequestException(
                    provider_name="anthropic",
                    error=ValueError(error_message)
                )
        return result

    async def list_models(self, api_key: str) -> list[str]:
        """List all models (verbosely) supported by the provider"""
        # Check cache first
        cached_models = self.get_cached_models(api_key, self._base_url)
        if cached_models is not None:
            return cached_models

        # If not in cache, make API call
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        url = f"{self._base_url}/models"

        async with (
            aiohttp.ClientSession() as session,
            session.get(url, headers=headers, params={"limit": 100}) as response,
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
            self.CLAUDE_MODEL_MAPPING = {
                d["display_name"]: d["id"] for d in resp["data"]
            }
            models = [d["id"] for d in resp["data"]]

            # Cache the results
            self.cache_models(api_key, self._base_url, models)

            return models

    async def process_completion(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> Any:
        """Process a completion request using Anthropic API"""
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # Convert OpenAI format to Anthropic format
        streaming = payload.get("stream", False)
        anthropic_payload = {
            "model": payload["model"],
            "max_tokens": payload.get("max_completion_tokens", payload.get("max_tokens", ANTHROPIC_DEFAULT_MAX_TOKENS)),
            "temperature": payload.get("temperature", 1.0),
            "stop_sequences": payload.get("stop", []),
        }

        # Handle chat vs. completion
        if "messages" in payload:
            # Use Anthropic's messages API format
            anthropic_messages = []
            system_message = None

            for msg in payload["messages"]:
                role = msg["role"]
                content = msg["content"]
                content = self.convert_openai_content_to_anthropic(content)

                if role == "system":
                    # Anthropic requires a system message to be string
                    # https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/system-prompts
                    assert isinstance(content, str)
                    system_message = content
                elif role == "user":
                    anthropic_messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    anthropic_messages.append({"role": "assistant", "content": content})

            # Add system message if present
            if system_message:
                anthropic_payload["system"] = system_message

            anthropic_payload["messages"] = anthropic_messages
        else:
            # Handle regular completion (legacy format)
            anthropic_payload["prompt"] = f"Human: {payload['prompt']}\n\nAssistant: "

        # Choose the appropriate API endpoint - using ternary operator
        api_endpoint = "messages" if "messages" in anthropic_payload else "complete"

        url = f"{self._base_url}/{api_endpoint}"

        # Handle streaming requests
        if streaming and "messages" in anthropic_payload:
            anthropic_payload["stream"] = True
            return await self._stream_anthropic_response(
                url, headers, anthropic_payload, payload["model"]
            )
        else:
            # For non-streaming, use the regular approach
            return await self._process_regular_response(
                url, headers, anthropic_payload, payload["model"]
            )

    async def _stream_anthropic_response(
        self, url, headers, anthropic_payload, model_name
    ):
        """Handle streaming response from Anthropic API, including usage data."""

        async def stream_response() -> AsyncGenerator[bytes, None]:
            # Store parts of usage info as they arrive
            captured_input_tokens = 0
            captured_output_tokens = 0
            usage_info_complete = False  # Flag to check if both are found
            request_id = f"chatcmpl-{uuid.uuid4()}"

            async with (
                aiohttp.ClientSession() as session,
                session.post(url, headers=headers, json=anthropic_payload) as response,
            ):
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    logger.error(f"Completion Streaming API error for {self.provider_name}: {error_text}")
                    raise ProviderAPIException(
                        provider_name=self.provider_name,
                        error_code=response.status,
                        error_message=error_text
                    )

                buffer = ""
                async for line_bytes in response.content:
                    decoded_line = line_bytes.decode("utf-8")
                    buffer += decoded_line
                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)
                        event_type = None
                        data_str = None
                        for line in event_str.strip().split("\n"):
                            if line.startswith("event:"):
                                event_type = line[len("event:") :].strip()
                            elif line.startswith("data:"):
                                data_str = line[len("data:") :].strip()

                        if not event_type or data_str is None:
                            continue

                        try:
                            data = json.loads(data_str)
                            openai_chunk = None
                            finish_reason = None
                            # --- Event Processing Logic ---

                            # Capture Input Tokens from message_start
                            if event_type == "message_start":
                                message_data = data.get("message", {})
                                if "usage" in message_data:
                                    captured_input_tokens = message_data["usage"].get(
                                        "input_tokens", 0
                                    )
                                    captured_output_tokens = message_data["usage"].get(
                                        "output_tokens", captured_output_tokens
                                    )

                            elif event_type == "content_block_delta":
                                delta_content = data.get("delta", {}).get("text", "")
                                if delta_content:
                                    openai_chunk = {
                                        "id": request_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": model_name,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {"content": delta_content},
                                                "finish_reason": None,
                                            }
                                        ],
                                    }

                            # Capture Output Tokens & Finish Reason from message_delta
                            elif event_type == "message_delta":
                                delta_data = data.get("delta", {})
                                finish_reason = delta_data.get(
                                    "stop_reason"
                                )  # Get finish reason from delta
                                if finish_reason:
                                    finish_reason = finish_reason.lower()

                                # Check for usage at the TOP LEVEL of the message_delta event data
                                if "usage" in data:
                                    usage_data_in_delta = data["usage"]
                                    captured_output_tokens = usage_data_in_delta.get(
                                        "output_tokens", captured_output_tokens
                                    )
                                    if captured_input_tokens > 0:
                                        usage_info_complete = True

                            # Capture Finish Reason from message_stop (backup for usage)
                            elif event_type == "message_stop":
                                finish_reason = data.get("stop_reason", "stop").lower()
                                if not usage_info_complete and "usage" in data:
                                    usage = data["usage"]
                                    captured_input_tokens = usage.get(
                                        "input_tokens", captured_input_tokens
                                    )
                                    captured_output_tokens = usage.get(
                                        "output_tokens", captured_output_tokens
                                    )
                                    if (
                                        captured_input_tokens > 0
                                        and captured_output_tokens > 0
                                    ):
                                        usage_info_complete = True

                            # --- Yielding Logic ---
                            if openai_chunk:
                                if finish_reason:
                                    openai_chunk["choices"][0][
                                        "finish_reason"
                                    ] = finish_reason
                                yield f"data: {json.dumps(openai_chunk)}\n\n".encode()

                            # Check if usage info is complete *after* potential content chunk
                            if usage_info_complete:
                                final_usage_data = {
                                    "prompt_tokens": captured_input_tokens,
                                    "completion_tokens": captured_output_tokens,
                                    "total_tokens": captured_input_tokens + captured_output_tokens,
                                }
                                usage_chunk = {
                                    "id": request_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model_name,
                                    "choices": [{"index": 0, "delta": {}}],
                                    "usage": final_usage_data,
                                }
                                yield f"data: {json.dumps(usage_chunk)}\n\n".encode()
                                # Reset flag to prevent duplicate yields
                                usage_info_complete = False

                        except json.JSONDecodeError as e:
                            logger.warning(f"Stream API error for {self.provider_name}: Failed to parse JSON: {e}")
                            continue
                        except Exception as e:
                            continue

            # Final SSE message
            yield b"data: [DONE]\n\n"

        return stream_response()

    async def _process_regular_response(
        self, url, headers, anthropic_payload, model_name
    ):
        """Handle regular (non-streaming) response from Anthropic API"""
        # Single with statement for multiple contexts
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, headers=headers, json=anthropic_payload) as response,
        ):
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                logger.error(f"Completion API error for {self.provider_name}: {error_text}")
                raise ProviderAPIException(
                    provider_name=self.provider_name,
                    error_code=response.status,
                    error_message=error_text
                )

            anthropic_response = await response.json()

            # Convert Anthropic response to OpenAI format
            completion_id = f"chatcmpl-{str(uuid.uuid4())}"
            created = int(time.time())

            if "messages" in anthropic_payload:
                # Messages API response
                content = anthropic_response.get("content", [])
                text_content = ""

                # Extract text from content blocks
                for block in content:
                    if block.get("type") == "text":
                        text_content += block.get("text", "")

                input_tokens = anthropic_response.get("usage", {}).get("input_tokens", 0)
                output_tokens = anthropic_response.get("usage", {}).get("output_tokens", 0)
                return {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": text_content,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                }
            else:
                # Legacy completion response
                return {
                    "id": completion_id,
                    "object": "text_completion",
                    "created": created,
                    "model": model_name,
                    "choices": [
                        {
                            "text": anthropic_response.get("completion", "").strip(),
                            "index": 0,
                            "logprobs": None,
                            "finish_reason": anthropic_response.get(
                                "stop_reason", "stop"
                            ),
                        }
                    ],
                    "usage": {
                        "prompt_tokens": -1,
                        "completion_tokens": -1,
                        "total_tokens": -1,
                    },
                }
    
    async def process_embeddings(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Process a embeddings request using Anthropic API"""
        # https://docs.anthropic.com/en/docs/build-with-claude/embeddings
        raise NotImplementedError("Anthropic does not support embeddings")
