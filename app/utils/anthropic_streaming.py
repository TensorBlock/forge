"""
Streaming utilities for converting OpenAI streaming responses to Anthropic SSE format.
Based on the streaming logic from convert.py but adapted for Forge's architecture.
"""

import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import tiktoken

from app.api.schemas.anthropic import ContentBlockText, ContentBlockToolUse
from app.core.logger import get_logger

logger = get_logger(name="anthropic_streaming")


async def handle_anthropic_streaming_response_from_openai_stream(
    openai_stream: AsyncGenerator[bytes, None],
    original_anthropic_model_name: str,
    estimated_input_tokens: int,
    request_id: str,
    start_time_mono: float,
) -> AsyncGenerator[str, None]:
    """
    Consumes an OpenAI stream and yields Anthropic-compatible SSE events.
    Handles content block indexing for mixed text/tool_use correctly.
    """
    
    anthropic_message_id = f"msg_stream_{request_id}_{uuid.uuid4().hex[:8]}"
    
    next_anthropic_block_idx = 0
    text_block_anthropic_idx: Optional[int] = None
    
    openai_tool_idx_to_anthropic_block_idx: Dict[int, int] = {}
    tool_states: Dict[int, Dict[str, Any]] = {}
    sent_tool_block_starts: set[int] = set()
    
    output_token_count = 0
    final_anthropic_stop_reason = None
    
    enc = tiktoken.encoding_for_model("gpt-4")  # Use gpt-4 encoding as approximation
    
    openai_to_anthropic_stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens", 
        "tool_calls": "tool_use",
        "function_call": "tool_use",
        "content_filter": "stop_sequence",
        None: None,
    }
    
    stream_status_code = 200
    stream_final_message = "Streaming request completed successfully."
    
    try:
        # Send initial message_start event
        message_start_event_data = {
            "type": "message_start",
            "message": {
                "id": anthropic_message_id,
                "type": "message",
                "role": "assistant",
                "model": original_anthropic_model_name,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": estimated_input_tokens, "output_tokens": 0},
            },
        }
        yield f"event: message_start\ndata: {json.dumps(message_start_event_data)}\n\n"
        yield f"event: ping\ndata: {json.dumps({'type': 'ping'})}\n\n"
        
        # Process the OpenAI stream
        async for chunk_bytes in openai_stream:
            try:
                chunk_str = chunk_bytes.decode('utf-8')
                if chunk_str.strip() == "data: [DONE]":
                    break
                    
                if not chunk_str.startswith("data: "):
                    continue
                    
                data_str = chunk_str[6:].strip()  # Remove "data: " prefix
                if not data_str:
                    continue
                    
                chunk_data = json.loads(data_str)
                
                if not chunk_data.get("choices"):
                    continue
                    
                delta = chunk_data["choices"][0].get("delta", {})
                openai_finish_reason = chunk_data["choices"][0].get("finish_reason")
                
                # Handle content delta
                if delta.get("content"):
                    content = delta["content"]
                    output_token_count += len(enc.encode(content))
                    
                    if text_block_anthropic_idx is None:
                        text_block_anthropic_idx = next_anthropic_block_idx
                        next_anthropic_block_idx += 1
                        
                        start_text_event = {
                            "type": "content_block_start",
                            "index": text_block_anthropic_idx,
                            "content_block": {"type": "text", "text": ""},
                        }
                        yield f"event: content_block_start\ndata: {json.dumps(start_text_event)}\n\n"
                    
                    text_delta_event = {
                        "type": "content_block_delta",
                        "index": text_block_anthropic_idx,
                        "delta": {"type": "text_delta", "text": content},
                    }
                    yield f"event: content_block_delta\ndata: {json.dumps(text_delta_event)}\n\n"
                
                # Handle tool calls delta
                if delta.get("tool_calls"):
                    for tool_delta in delta["tool_calls"]:
                        openai_tc_idx = tool_delta.get("index", 0)
                        
                        if openai_tc_idx not in openai_tool_idx_to_anthropic_block_idx:
                            current_anthropic_tool_block_idx = next_anthropic_block_idx
                            next_anthropic_block_idx += 1
                            openai_tool_idx_to_anthropic_block_idx[openai_tc_idx] = current_anthropic_tool_block_idx
                            
                            tool_states[current_anthropic_tool_block_idx] = {
                                "id": tool_delta.get("id") or f"tool_ph_{request_id}_{current_anthropic_tool_block_idx}",
                                "name": "",
                                "arguments_buffer": "",
                            }
                        else:
                            current_anthropic_tool_block_idx = openai_tool_idx_to_anthropic_block_idx[openai_tc_idx]
                        
                        tool_state = tool_states[current_anthropic_tool_block_idx]
                        
                        # Update tool ID if provided
                        if tool_delta.get("id") and tool_state["id"].startswith("tool_ph_"):
                            tool_state["id"] = tool_delta["id"]
                        
                        # Update function details
                        if tool_delta.get("function"):
                            if tool_delta["function"].get("name"):
                                tool_state["name"] = tool_delta["function"]["name"]
                            if tool_delta["function"].get("arguments"):
                                args_chunk = tool_delta["function"]["arguments"]
                                tool_state["arguments_buffer"] += args_chunk
                                output_token_count += len(enc.encode(args_chunk))
                        
                        # Send content_block_start for tools when we have enough info
                        if (
                            current_anthropic_tool_block_idx not in sent_tool_block_starts
                            and tool_state["id"]
                            and not tool_state["id"].startswith("tool_ph_")
                            and tool_state["name"]
                        ):
                            start_tool_event = {
                                "type": "content_block_start",
                                "index": current_anthropic_tool_block_idx,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": tool_state["id"],
                                    "name": tool_state["name"],
                                    "input": {},
                                },
                            }
                            yield f"event: content_block_start\ndata: {json.dumps(start_tool_event)}\n\n"
                            sent_tool_block_starts.add(current_anthropic_tool_block_idx)
                        
                        # Send delta for tool arguments
                        if (
                            tool_delta.get("function", {}).get("arguments")
                            and current_anthropic_tool_block_idx in sent_tool_block_starts
                        ):
                            args_delta_event = {
                                "type": "content_block_delta",
                                "index": current_anthropic_tool_block_idx,
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": tool_delta["function"]["arguments"],
                                },
                            }
                            yield f"event: content_block_delta\ndata: {json.dumps(args_delta_event)}\n\n"
                
                # Handle finish reason
                if openai_finish_reason:
                    final_anthropic_stop_reason = openai_to_anthropic_stop_reason_map.get(
                        openai_finish_reason, "end_turn"
                    )
                    if openai_finish_reason == "tool_calls":
                        final_anthropic_stop_reason = "tool_use"
                    break
                    
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse chunk: {chunk_str}")
                continue
            except Exception as e:
                logger.error(f"Error processing stream chunk: {e}")
                continue
        
        # Send content_block_stop events
        if text_block_anthropic_idx is not None:
            yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': text_block_anthropic_idx})}\n\n"
        
        for anthropic_tool_idx in sent_tool_block_starts:
            tool_state_to_finalize = tool_states.get(anthropic_tool_idx)
            if tool_state_to_finalize:
                try:
                    json.loads(tool_state_to_finalize["arguments_buffer"])
                except json.JSONDecodeError:
                    logger.warning(
                        f"Buffered arguments for tool '{tool_state_to_finalize.get('name')}' did not form valid JSON"
                    )
            yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': anthropic_tool_idx})}\n\n"
        
        if final_anthropic_stop_reason is None:
            final_anthropic_stop_reason = "end_turn"
        
        # Send final events
        message_delta_event = {
            "type": "message_delta",
            "delta": {
                "stop_reason": final_anthropic_stop_reason,
                "stop_sequence": None,
            },
            "usage": {"output_tokens": output_token_count},
        }
        yield f"event: message_delta\ndata: {json.dumps(message_delta_event)}\n\n"
        yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
        
    except Exception as e:
        stream_status_code = 500
        final_anthropic_stop_reason = "error"
        
        logger.error(f"Error during OpenAI stream conversion: {e}")
        
        # Send error event
        error_event = {
            "type": "error",
            "error": {
                "type": "api_error", 
                "message": f"Stream processing error: {str(e)}",
            }
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
    
    finally:
        duration_ms = (time.monotonic() - start_time_mono) * 1000
        log_data = {
            "status_code": stream_status_code,
            "duration_ms": duration_ms,
            "input_tokens": estimated_input_tokens,
            "output_tokens": output_token_count,
            "stop_reason": final_anthropic_stop_reason,
        }
        
        if stream_status_code == 200:
            logger.info(f"Streaming request completed successfully: {log_data}")
        else:
            logger.error(f"Streaming request failed: {log_data}") 