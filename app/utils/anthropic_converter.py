"""
Conversion utilities between Anthropic and OpenAI formats for Claude Code support.
Based on the conversion logic from convert.py but adapted for Forge's architecture.
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Union

import tiktoken

from app.api.schemas.anthropic import (
    AnthropicMessage,
    AnthropicMessagesResponse,
    ContentBlock,
    ContentBlockText,
    ContentBlockImage,
    ContentBlockToolUse,
    ContentBlockToolResult,
    SystemContent,
    Tool,
    ToolChoice,
    Usage,
)
from app.api.schemas.openai import ChatMessage, OpenAIContentModel
from app.core.logger import get_logger

logger = get_logger(name="anthropic_converter")

# Token encoder cache
_token_encoder_cache: Dict[str, tiktoken.Encoding] = {}


def get_token_encoder(model_name: str = "gpt-4", request_id: Optional[str] = None) -> tiktoken.Encoding:
    """Gets a tiktoken encoder, caching it for performance."""
    cache_key = "gpt-4"
    if cache_key not in _token_encoder_cache:
        try:
            _token_encoder_cache[cache_key] = tiktoken.encoding_for_model(cache_key)
        except Exception:
            try:
                _token_encoder_cache[cache_key] = tiktoken.get_encoding("cl100k_base")
                logger.warning(
                    f"Could not load tiktoken encoder for '{cache_key}', using 'cl100k_base'. Token counts may be approximate."
                )
            except Exception as e:
                logger.error(f"Failed to load any tiktoken encoder. Token counting will be inaccurate: {e}")
                
                class DummyEncoder:
                    def encode(self, text: str) -> List[int]:
                        return list(range(len(text)))

                _token_encoder_cache[cache_key] = DummyEncoder()
    return _token_encoder_cache[cache_key]


def count_tokens_for_anthropic_request(
    messages: List[AnthropicMessage],
    system: Optional[Union[str, List[SystemContent]]],
    model_name: str,
    tools: Optional[List[Tool]] = None,
    request_id: Optional[str] = None,
) -> int:
    """Count tokens for an Anthropic request."""
    enc = get_token_encoder(model_name, request_id)
    total_tokens = 0

    # Count system message tokens
    if isinstance(system, str):
        total_tokens += len(enc.encode(system))
    elif isinstance(system, list):
        for block in system:
            if isinstance(block, SystemContent) and block.type == "text":
                total_tokens += len(enc.encode(block.text))

    # Count message tokens
    for msg in messages:
        total_tokens += 4  # Base tokens per message
        if msg.role:
            total_tokens += len(enc.encode(msg.role))

        if isinstance(msg.content, str):
            total_tokens += len(enc.encode(msg.content))
        elif isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, ContentBlockText):
                    total_tokens += len(enc.encode(block.text))
                elif isinstance(block, ContentBlockImage):
                    total_tokens += 768  # Estimated tokens for image
                elif isinstance(block, ContentBlockToolUse):
                    total_tokens += len(enc.encode(block.name))
                    try:
                        input_str = json.dumps(block.input)
                        total_tokens += len(enc.encode(input_str))
                    except Exception:
                        logger.warning(f"Failed to serialize tool input for token counting: {block.name}")
                elif isinstance(block, ContentBlockToolResult):
                    try:
                        content_str = ""
                        if isinstance(block.content, str):
                            content_str = block.content
                        elif isinstance(block.content, list):
                            for item in block.content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    content_str += item.get("text", "")
                                else:
                                    content_str += json.dumps(item)
                        else:
                            content_str = json.dumps(block.content)
                        total_tokens += len(enc.encode(content_str))
                    except Exception:
                        logger.warning("Failed to serialize tool result for token counting")

    # Count tool tokens
    if tools:
        total_tokens += 2
        for tool in tools:
            total_tokens += len(enc.encode(tool.name))
            if tool.description:
                total_tokens += len(enc.encode(tool.description))
            try:
                schema_str = json.dumps(tool.input_schema)
                total_tokens += len(enc.encode(schema_str))
            except Exception:
                logger.warning(f"Failed to serialize tool schema for token counting: {tool.name}")

    logger.debug(f"Estimated {total_tokens} input tokens for model {model_name}")
    return total_tokens


def _serialize_tool_result_content_for_openai(
    anthropic_tool_result_content: Union[str, List[Dict[str, Any]], List[Any]],
    request_id: Optional[str],
) -> str:
    """Serializes Anthropic tool result content into a single string for OpenAI."""
    if isinstance(anthropic_tool_result_content, str):
        return anthropic_tool_result_content

    if isinstance(anthropic_tool_result_content, list):
        processed_parts = []
        contains_non_text_block = False
        for item in anthropic_tool_result_content:
            if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
                processed_parts.append(str(item["text"]))
            else:
                try:
                    processed_parts.append(json.dumps(item))
                    contains_non_text_block = True
                except TypeError:
                    processed_parts.append(f"<unserializable_item type='{type(item).__name__}'>")
                    contains_non_text_block = True

        result_str = "\n".join(processed_parts)
        if contains_non_text_block:
            logger.warning(
                f"Tool result content list contained non-text or complex items; parts were JSON stringified. Preview: {result_str[:100]}"
            )
        return result_str

    try:
        return json.dumps(anthropic_tool_result_content)
    except TypeError as e:
        logger.warning(f"Failed to serialize tool result content to JSON: {e}")
        return json.dumps({
            "error": "Serialization failed",
            "original_type": str(type(anthropic_tool_result_content)),
        })


def convert_anthropic_to_openai_messages(
    anthropic_messages: List[AnthropicMessage],
    anthropic_system: Optional[Union[str, List[SystemContent]]] = None,
    request_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convert Anthropic messages to OpenAI format."""
    openai_messages: List[Dict[str, Any]] = []

    # Handle system message
    system_text_content = ""
    if isinstance(anthropic_system, str):
        system_text_content = anthropic_system
    elif isinstance(anthropic_system, list):
        system_texts = [
            block.text
            for block in anthropic_system
            if isinstance(block, SystemContent) and block.type == "text"
        ]
        if len(system_texts) < len(anthropic_system):
            logger.warning("Non-text content blocks in Anthropic system prompt were ignored")
        system_text_content = "\n".join(system_texts)

    if system_text_content:
        openai_messages.append({"role": "system", "content": system_text_content})

    # Convert messages
    for i, msg in enumerate(anthropic_messages):
        role = msg.role
        content = msg.content

        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            openai_parts_for_user_message = []
            assistant_tool_calls = []
            text_content_for_assistant = []

            if not content and role == "user":
                openai_messages.append({"role": "user", "content": ""})
                continue
            if not content and role == "assistant":
                openai_messages.append({"role": "assistant", "content": ""})
                continue

            for block_idx, block in enumerate(content):
                if isinstance(block, ContentBlockText):
                    if role == "user":
                        openai_parts_for_user_message.append({"type": "text", "text": block.text})
                    elif role == "assistant":
                        text_content_for_assistant.append(block.text)

                elif isinstance(block, ContentBlockImage) and role == "user":
                    if block.source.type == "base64":
                        openai_parts_for_user_message.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{block.source.media_type};base64,{block.source.data}"
                            },
                        })
                    else:
                        logger.warning(
                            f"Image block with source type '{block.source.type}' (expected 'base64') ignored in user message {i}"
                        )

                elif isinstance(block, ContentBlockToolUse) and role == "assistant":
                    try:
                        args_str = json.dumps(block.input)
                    except Exception as e:
                        logger.error(f"Failed to serialize tool input for tool '{block.name}': {e}")
                        args_str = "{}"

                    assistant_tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {"name": block.name, "arguments": args_str},
                    })

                elif isinstance(block, ContentBlockToolResult) and role == "user":
                    serialized_content = _serialize_tool_result_content_for_openai(
                        block.content, request_id
                    )
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": block.tool_use_id,
                        "content": serialized_content,
                    })

            # Handle user message parts
            if role == "user" and openai_parts_for_user_message:
                is_multimodal = any(
                    part["type"] == "image_url" for part in openai_parts_for_user_message
                )
                if is_multimodal or len(openai_parts_for_user_message) > 1:
                    openai_messages.append({"role": "user", "content": openai_parts_for_user_message})
                elif (
                    len(openai_parts_for_user_message) == 1
                    and openai_parts_for_user_message[0]["type"] == "text"
                ):
                    openai_messages.append({
                        "role": "user",
                        "content": openai_parts_for_user_message[0]["text"],
                    })
                elif not openai_parts_for_user_message:
                    openai_messages.append({"role": "user", "content": ""})

            # Handle assistant message
            if role == "assistant":
                assistant_text = "\n".join(filter(None, text_content_for_assistant))
                if assistant_text:
                    openai_messages.append({"role": "assistant", "content": assistant_text})

                if assistant_tool_calls:
                    if (
                        openai_messages
                        and openai_messages[-1]["role"] == "assistant"
                        and openai_messages[-1].get("content")
                    ):
                        openai_messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": assistant_tool_calls,
                        })
                    elif (
                        openai_messages
                        and openai_messages[-1]["role"] == "assistant"
                        and not openai_messages[-1].get("tool_calls")
                    ):
                        openai_messages[-1]["tool_calls"] = assistant_tool_calls
                        openai_messages[-1]["content"] = None
                    else:
                        openai_messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": assistant_tool_calls,
                        })

    # Clean up messages
    final_openai_messages = []
    for msg_dict in openai_messages:
        if (
            msg_dict.get("role") == "assistant"
            and msg_dict.get("tool_calls")
            and msg_dict.get("content") is not None
        ):
            logger.warning("Corrected assistant message with tool_calls to have content: None")
            msg_dict["content"] = None
        final_openai_messages.append(msg_dict)

    return final_openai_messages


def convert_anthropic_tools_to_openai(
    anthropic_tools: Optional[List[Tool]],
) -> Optional[List[Dict[str, Any]]]:
    """Convert Anthropic tools to OpenAI format."""
    if not anthropic_tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            },
        }
        for t in anthropic_tools
    ]


def convert_anthropic_tool_choice_to_openai(
    anthropic_choice: Optional[ToolChoice],
    request_id: Optional[str] = None,
) -> Optional[Union[str, Dict[str, Any]]]:
    """Convert Anthropic tool choice to OpenAI format."""
    if not anthropic_choice:
        return None
    if anthropic_choice.type == "auto":
        return "auto"
    if anthropic_choice.type == "any":
        logger.warning(
            "Anthropic tool_choice type 'any' mapped to OpenAI 'auto'. Exact behavior might differ"
        )
        return "auto"
    if anthropic_choice.type == "tool" and anthropic_choice.name:
        return {"type": "function", "function": {"name": anthropic_choice.name}}

    logger.warning(f"Unsupported Anthropic tool_choice: {anthropic_choice}. Defaulting to 'auto'")
    return "auto"


def convert_openai_to_anthropic_response(
    openai_response: Dict[str, Any],
    original_anthropic_model_name: str,
    request_id: Optional[str] = None,
) -> AnthropicMessagesResponse:
    """Convert OpenAI response to Anthropic format."""
    anthropic_content: List[ContentBlock] = []
    anthropic_stop_reason = None

    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "function_call": "tool_use",
        "content_filter": "stop_sequence",
        None: "end_turn",
    }

    if openai_response.get("choices"):
        choice = openai_response["choices"][0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason")

        anthropic_stop_reason = stop_reason_map.get(finish_reason, "end_turn")

        # Handle text content
        if message.get("content"):
            anthropic_content.append(ContentBlockText(type="text", text=message["content"]))

        # Handle tool calls
        if message.get("tool_calls"):
            for i, call in enumerate(message["tool_calls"]):
                if call.get("type") == "function":
                    tool_input_dict: Dict[str, Any] = {}
                    try:
                        parsed_input = json.loads(call["function"]["arguments"])
                        if isinstance(parsed_input, dict):
                            tool_input_dict = parsed_input
                        else:
                            tool_input_dict = {"value": parsed_input}
                            logger.warning(
                                f"OpenAI tool arguments for '{call['function']['name']}' parsed to non-dict type. Wrapped in 'value'"
                            )
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON arguments for tool '{call['function']['name']}': {e}")
                        tool_input_dict = {"error_parsing_arguments": call["function"]["arguments"]}

                    # Handle empty tool ID by generating a placeholder, similar to streaming logic
                    tool_id = call.get("id")
                    if not tool_id or tool_id.strip() == "":
                        tool_id = f"tool_ph_{request_id}_{i}" if request_id else f"tool_ph_{uuid.uuid4().hex}_{i}"
                        logger.debug(
                            f"Generated placeholder tool ID '{tool_id}' for tool '{call['function']['name']}' due to empty ID from provider",
                            extra={"request_id": request_id} if request_id else {}
                        )

                    anthropic_content.append(ContentBlockToolUse(
                        type="tool_use",
                        id=tool_id,
                        name=call["function"]["name"],
                        input=tool_input_dict,
                    ))
            if finish_reason == "tool_calls":
                anthropic_stop_reason = "tool_use"

    if not anthropic_content:
        anthropic_content.append(ContentBlockText(type="text", text=""))

    usage = openai_response.get("usage", {})
    anthropic_usage = Usage(
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )

    response_id = openai_response.get("id", f"msg_{request_id}_completed")
    if not response_id.startswith("msg_"):
        response_id = f"msg_{response_id}"

    return AnthropicMessagesResponse(
        id=response_id,
        type="message",
        role="assistant",
        model=original_anthropic_model_name,
        content=anthropic_content,
        stop_reason=anthropic_stop_reason,
        usage=anthropic_usage,
    ) 