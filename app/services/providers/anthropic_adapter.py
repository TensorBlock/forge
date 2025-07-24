import json
import time
import uuid
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any, Callable

import aiohttp

from app.core.logger import get_logger
from app.exceptions.exceptions import (
    ProviderAPIException,
    InvalidCompletionRequestException,
)

from .base import ProviderAdapter

logger = get_logger(name="anthropic_adapter")

ANTHROPIC_DEFAULT_MAX_TOKENS = 4096

logger = get_logger(name="anthropic_adapter")


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
        content: list[dict[str, Any]] | str | None,
    ) -> list[dict[str, Any]] | str:
        """Convert OpenAI content model to Anthropic content model"""
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if not isinstance(content, list):
            return str(content)

        result = []
        for msg in content:
            if not msg or not isinstance(msg, dict):
                continue

            _type = msg.get("type")
            if _type == "text":
                result.append({"type": "text", "text": msg.get("text", "")})
            elif _type == "image_url":
                result.append(
                    AnthropicAdapter.convert_openai_image_content_to_anthropic(msg)
                )
            else:
                error_message = f"{_type} is not supported"
                logger.error(error_message)
                raise InvalidCompletionRequestException(
                    provider_name="anthropic", error=ValueError(error_message)
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
                logger.error(
                    f"List Models API error for {self.provider_name}: {error_text}"
                )
                raise ProviderAPIException(
                    provider_name=self.provider_name,
                    error_code=response.status,
                    error_message=error_text,
                )
            resp = await response.json()
            self.CLAUDE_MODEL_MAPPING = {
                d["display_name"]: d["id"] for d in resp["data"]
            }
            models = [d["id"] for d in resp["data"]]

            # Cache the results
            self.cache_models(api_key, self._base_url, models)

            return models

    @staticmethod
    def convert_openai_payload_to_anthropic(payload: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI completion payload to Anthropic format"""
        anthropic_payload = {
            "model": payload["model"],
            "max_tokens": payload.get(
                "max_completion_tokens",
                payload.get("max_tokens", ANTHROPIC_DEFAULT_MAX_TOKENS),
            ),
            "temperature": payload.get("temperature", 1.0),
        }

        # Handle optional parameters
        if payload.get("top_p") is not None:
            anthropic_payload["top_p"] = payload["top_p"]
        if payload.get("top_k") is not None:
            anthropic_payload["top_k"] = payload["top_k"]
        if payload.get("stream") is not None:
            anthropic_payload["stream"] = payload["stream"]
        if payload.get("stop"):
            anthropic_payload["stop_sequences"] = (
                payload["stop"]
                if isinstance(payload["stop"], list)
                else [payload["stop"]]
            )

        # Convert tools if present
        tools = payload.get("tools")
        if tools:
            anthropic_tools = []
            for tool in tools:
                if not tool or not isinstance(tool, dict):
                    continue

                if tool.get("type") == "function" and tool.get("function"):
                    func = tool.get("function", {})
                    if not func or not isinstance(func, dict):
                        continue

                    params = func.get("parameters", {})
                    if params is None:
                        params = {}

                    anthropic_tool = {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "input_schema": {
                            "type": params.get("type", "object"),
                            "properties": params.get("properties", {}),
                        },
                    }
                    required = params.get("required")
                    if required and isinstance(required, list):
                        anthropic_tool["input_schema"]["required"] = required

                    anthropic_tools.append(anthropic_tool)

            if anthropic_tools:
                anthropic_payload["tools"] = anthropic_tools

                # Handle tool_choice conversion
                tool_choice = payload.get("tool_choice")
                if tool_choice:
                    if isinstance(tool_choice, str):
                        if tool_choice == "auto":
                            anthropic_payload["tool_choice"] = {"type": "auto"}
                        elif tool_choice == "any":
                            anthropic_payload["tool_choice"] = {"type": "any"}
                        elif tool_choice == "none":
                            # Anthropic doesn't have explicit "none", just omit tools
                            pass
                    elif (
                        isinstance(tool_choice, dict)
                        and tool_choice.get("type") == "function"
                    ):
                        func_choice = tool_choice.get("function", {})
                        anthropic_payload["tool_choice"] = {
                            "type": "tool",
                            "name": func_choice.get("name"),
                        }
                else:
                    # Default to auto when tools are present
                    anthropic_payload["tool_choice"] = {"type": "auto"}

        # Handle chat vs. completion
        if "messages" in payload:
            # Use Anthropic's messages API format
            anthropic_messages = []
            system_message = None

            for msg in payload["messages"]:
                role = msg["role"]
                content = msg["content"]

                if role == "system":
                    # Anthropic requires a system message to be string
                    if isinstance(content, str):
                        system_message = content
                    elif isinstance(content, list):
                        # Extract text from content blocks
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                        system_message = "\n".join(text_parts)
                    continue

                elif role == "tool":
                    # Tool responses should be converted to user messages with tool_result content
                    tool_call_id = msg.get("tool_call_id", "")
                    tool_content = content if isinstance(content, str) else str(content)

                    anthropic_messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_call_id,
                                    "content": tool_content,
                                }
                            ],
                        }
                    )
                    continue

                # Convert content for user/assistant messages
                if isinstance(content, str):
                    anthropic_content = content
                else:
                    anthropic_content = (
                        AnthropicAdapter.convert_openai_content_to_anthropic(content)
                    )

                anthropic_message = {"role": role, "content": anthropic_content}

                # Handle tool calls in assistant messages
                tool_calls = msg.get("tool_calls")
                if role == "assistant" and tool_calls:
                    # Ensure content is a list for tool calls
                    if isinstance(anthropic_content, str):
                        if anthropic_content and anthropic_content.strip():
                            message_content = [
                                {"type": "text", "text": anthropic_content}
                            ]
                        else:
                            message_content = []
                    else:
                        message_content = (
                            anthropic_content
                            if isinstance(anthropic_content, list)
                            else []
                        )

                    # Add tool use blocks - ensure tool_calls is not None
                    if tool_calls is not None:
                        for tool_call in tool_calls:
                            if tool_call and tool_call.get("type") == "function":
                                func = tool_call.get("function", {})
                                if func:  # Ensure function is not None
                                    try:
                                        # Parse arguments JSON
                                        args_str = func.get("arguments", "{}")
                                        args = json.loads(args_str) if args_str else {}
                                    except json.JSONDecodeError:
                                        logger.warning(
                                            f"Failed to parse tool call arguments: {func.get('arguments')}"
                                        )
                                        args = {}

                                    message_content.append(
                                        {
                                            "type": "tool_use",
                                            "id": tool_call.get(
                                                "id", f"tool_{uuid.uuid4().hex[:8]}"
                                            ),
                                            "name": func.get("name", ""),
                                            "input": args,
                                        }
                                    )

                    anthropic_message["content"] = message_content

                anthropic_messages.append(anthropic_message)

            # Add system message if present
            if system_message:
                anthropic_payload["system"] = system_message

            anthropic_payload["messages"] = anthropic_messages
        else:
            # Handle regular completion (legacy format)
            anthropic_payload["prompt"] = f"Human: {payload['prompt']}\n\nAssistant: "

        return anthropic_payload

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

        streaming = payload.get("stream", False)
        # Convert OpenAI format to Anthropic format
        anthropic_payload = self.convert_openai_payload_to_anthropic(payload)

        # Choose the appropriate API endpoint - using ternary operator
        api_endpoint = "messages" if "messages" in anthropic_payload else "complete"

        url = f"{self._base_url}/{api_endpoint}"

        # Handle streaming requests
        if streaming and "messages" in anthropic_payload:
            anthropic_payload["stream"] = True
            return await self.stream_anthropic_response(
                url, headers, anthropic_payload, payload["model"]
            )
        else:
            # For non-streaming, use the regular approach
            return await self.process_regular_response(
                url, headers, anthropic_payload, payload["model"]
            )

    @staticmethod
    async def stream_anthropic_response(
        url,
        headers,
        anthropic_payload,
        model_name,
        error_handler: Callable[[str, int], Any] | None = None,
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
                    if error_handler:
                        error_handler(error_text, response.status)
                    else:
                        logger.error(f"Completion API error for {error_text}")
                        raise ProviderAPIException(
                            provider_name="anthropic",
                            error_code=response.status,
                            error_message=error_text,
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

                            elif event_type == "content_block_start":
                                # Handle start of content blocks (text or tool_use)
                                content_block = data.get("content_block", {})
                                if content_block.get("type") == "tool_use":
                                    # Start of a tool call
                                    openai_chunk = {
                                        "id": request_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": model_name,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {
                                                    "tool_calls": [
                                                        {
                                                            "index": data.get(
                                                                "index", 0
                                                            ),
                                                            "id": content_block.get(
                                                                "id",
                                                                f"call_{uuid.uuid4().hex[:8]}",
                                                            ),
                                                            "type": "function",
                                                            "function": {
                                                                "name": content_block.get(
                                                                    "name", ""
                                                                ),
                                                                "arguments": "",
                                                            },
                                                        }
                                                    ]
                                                },
                                                "finish_reason": None,
                                            }
                                        ],
                                    }

                            elif event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    # Text content delta
                                    delta_content = delta.get("text", "")
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
                                elif delta.get("type") == "input_json_delta":
                                    # Tool arguments delta
                                    partial_json = delta.get("partial_json", "")
                                    if partial_json:
                                        openai_chunk = {
                                            "id": request_id,
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": model_name,
                                            "choices": [
                                                {
                                                    "index": 0,
                                                    "delta": {
                                                        "tool_calls": [
                                                            {
                                                                "index": data.get(
                                                                    "index", 0
                                                                ),
                                                                "function": {
                                                                    "arguments": partial_json
                                                                },
                                                            }
                                                        ]
                                                    },
                                                    "finish_reason": None,
                                                }
                                            ],
                                        }

                            # Capture Output Tokens & Finish Reason from message_delta
                            elif event_type == "message_delta":
                                delta_data = data.get("delta", {})
                                anthropic_stop_reason = delta_data.get("stop_reason")
                                if anthropic_stop_reason:
                                    # Map Anthropic stop reason to OpenAI finish reason
                                    finish_reason_map = {
                                        "end_turn": "stop",
                                        "stop_sequence": "stop",
                                        "max_tokens": "length",
                                        "tool_use": "tool_calls",
                                    }
                                    finish_reason = finish_reason_map.get(
                                        anthropic_stop_reason, "stop"
                                    )

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
                                # Map Anthropic stop reason to OpenAI finish reason if not already set
                                if not finish_reason:
                                    anthropic_stop_reason = data.get(
                                        "stop_reason", "end_turn"
                                    )
                                    finish_reason_map = {
                                        "end_turn": "stop",
                                        "stop_sequence": "stop",
                                        "max_tokens": "length",
                                        "tool_use": "tool_calls",
                                    }
                                    finish_reason = finish_reason_map.get(
                                        anthropic_stop_reason, "stop"
                                    )

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
                                    openai_chunk["choices"][0]["finish_reason"] = (
                                        finish_reason
                                    )
                                yield f"data: {json.dumps(openai_chunk)}\n\n".encode()

                            # Check if usage info is complete *after* potential content chunk
                            if usage_info_complete:
                                final_usage_data = {
                                    "prompt_tokens": captured_input_tokens,
                                    "completion_tokens": captured_output_tokens,
                                    "total_tokens": captured_input_tokens
                                    + captured_output_tokens,
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
                            logger.warning(
                                f"Stream API error for {self.provider_name}: Failed to parse JSON: {e}"
                            )
                            continue
                        except Exception as e:
                            continue

            # Final SSE message
            yield b"data: [DONE]\n\n"

        return stream_response()

    @staticmethod
    async def process_regular_response(
        url: str,
        headers: dict[str, str],
        anthropic_payload: dict[str, Any],
        model_name: str,
        error_handler: Callable[[str, int], Any] | None = None,
    ):
        """Handle regular (non-streaming) response from Anthropic API"""
        # Single with statement for multiple contexts
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, headers=headers, json=anthropic_payload) as response,
        ):
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                logger.error(f"Completion API error for {error_text}")
                raise ProviderAPIException(
                    provider_name="anthropic",
                    error_code=response.status,
                    error_message=error_text,
                )

            anthropic_response = await response.json()

            # Convert Anthropic response to OpenAI format
            completion_id = f"chatcmpl-{str(uuid.uuid4())}"
            created = int(time.time())

            if "messages" in anthropic_payload:
                # Messages API response
                content = anthropic_response.get("content", [])
                text_content = ""
                tool_calls = []

                # Extract text and tool calls from content blocks
                if content:  # Ensure content is not None
                    for block in content:
                        if not block or not isinstance(block, dict):
                            continue

                        if block.get("type") == "text":
                            text_content += block.get("text", "")
                        elif block.get("type") == "tool_use":
                            # Convert Anthropic tool use to OpenAI tool call format
                            tool_calls.append(
                                {
                                    "id": block.get(
                                        "id", f"call_{uuid.uuid4().hex[:8]}"
                                    ),
                                    "type": "function",
                                    "function": {
                                        "name": block.get("name", ""),
                                        "arguments": json.dumps(block.get("input", {})),
                                    },
                                }
                            )

                # Map Anthropic stop reason to OpenAI finish reason
                stop_reason = anthropic_response.get("stop_reason", "end_turn")
                finish_reason_map = {
                    "end_turn": "stop",
                    "stop_sequence": "stop",
                    "max_tokens": "length",
                    "tool_use": "tool_calls",
                }
                finish_reason = finish_reason_map.get(stop_reason, "stop")

                # Build message content
                message_content = {
                    "role": "assistant",
                    "content": text_content if text_content else None,
                }

                # Add tool calls if present
                if tool_calls:
                    message_content["tool_calls"] = tool_calls
                    if not text_content:
                        message_content["content"] = (
                            None  # OpenAI expects null content when tool calls are present
                        )

                input_tokens = anthropic_response.get("usage", {}).get(
                    "input_tokens", 0
                )
                output_tokens = anthropic_response.get("usage", {}).get(
                    "output_tokens", 0
                )
                return {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "message": message_content,
                            "finish_reason": finish_reason,
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
