"""
Claude Code compatible API endpoints.
Handles Anthropic format requests and converts them to/from OpenAI format via Forge's infrastructure.
"""

import inspect
import json
import time
import uuid
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_user_by_api_key, get_user_details_by_api_key
from app.api.routes.proxy import _get_allowed_provider_names
from app.api.schemas.anthropic import (
    AnthropicErrorResponse,
    AnthropicErrorType,
    AnthropicMessagesRequest,
    AnthropicMessagesResponse,
    TokenCountRequest,
    TokenCountResponse,
)
from app.core.database import get_async_db
from app.core.logger import get_logger
from app.models.user import User
from app.services.provider_service import ProviderService
from app.utils.anthropic_converter import (
    convert_anthropic_to_openai_messages,
    convert_anthropic_tools_to_openai,
    convert_anthropic_tool_choice_to_openai,
    convert_openai_to_anthropic_response,
    count_tokens_for_anthropic_request,
)
from app.utils.anthropic_streaming import handle_anthropic_streaming_response_from_openai_stream

router = APIRouter()
logger = get_logger(name="claude_code")


def _build_anthropic_error_response(
    error_type: str,
    message: str,
    status_code: int,
) -> JSONResponse:
    """Creates a JSONResponse with Anthropic-formatted error."""
    error_resp_model = AnthropicErrorResponse(
        error={
            "type": error_type,
            "message": message,
        }
    )
    return JSONResponse(
        status_code=status_code, 
        content=error_resp_model.model_dump(exclude_unset=True)
    )


async def _log_and_return_error_response(
    request: Request,
    status_code: int,
    anthropic_error_type: str,
    error_message: str,
    caught_exception: Exception = None,
) -> JSONResponse:
    """Log error and return Anthropic-formatted error response."""
    request_id = getattr(request.state, "request_id", "unknown")
    start_time_mono = getattr(request.state, "start_time_monotonic", time.monotonic())
    duration_ms = (time.monotonic() - start_time_mono) * 1000

    log_data = {
        "status_code": status_code,
        "duration_ms": duration_ms,
        "error_type": anthropic_error_type,
        "client_ip": request.client.host if request.client else "unknown",
    }

    if caught_exception:
        logger.error(
            f"Claude Code request failed: {error_message}",
            extra={"request_id": request_id, "data": log_data},
            exc_info=caught_exception,
        )
    else:
        logger.error(
            f"Claude Code request failed: {error_message}",
            extra={"request_id": request_id, "data": log_data},
        )

    return _build_anthropic_error_response(
        anthropic_error_type, error_message, status_code
    )


@router.post("/messages", response_model=None, tags=["Claude Code"], status_code=200)
async def create_message_proxy(
    request: Request,
    user_details: dict[str, Any] = Depends(get_user_details_by_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> Union[JSONResponse, StreamingResponse]:
    """
    Main endpoint for Claude Code message completions, proxied through Forge to providers.
    Handles request/response conversions, streaming, and dynamic model selection.
    """
    user = user_details["user"]
    api_key_id = user_details["api_key_id"]

    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.start_time_monotonic = time.monotonic()

    try:
        # Parse request body
        raw_body = await request.json()
        logger.debug(
            "Received Claude Code request body",
            extra={
                "request_id": request_id,
                "data": {"body": raw_body},
            },
        )

        anthropic_request = AnthropicMessagesRequest.model_validate(raw_body)
    except json.JSONDecodeError as e:
        return await _log_and_return_error_response(
            request,
            400,
            AnthropicErrorType.INVALID_REQUEST,
            "Invalid JSON body.",
            e,
        )
    except ValidationError as e:
        return await _log_and_return_error_response(
            request,
            422,
            AnthropicErrorType.INVALID_REQUEST,
            f"Invalid request body: {str(e.errors())}",
            e,
        )

    is_stream = anthropic_request.stream or False

    # Count tokens for logging
    estimated_input_tokens = count_tokens_for_anthropic_request(
        messages=anthropic_request.messages,
        system=anthropic_request.system,
        model_name=anthropic_request.model,
        tools=anthropic_request.tools,
        request_id=request_id,
    )

    logger.info(
        "Processing new Claude Code message request",
        extra={
            "request_id": request_id,
            "data": {
                "model": anthropic_request.model,
                "stream": is_stream,
                "estimated_input_tokens": estimated_input_tokens,
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown"),
            },
        },
    )

    try:
        # Convert Anthropic format to OpenAI format
        openai_messages = convert_anthropic_to_openai_messages(
            anthropic_request.messages, 
            anthropic_request.system, 
            request_id=request_id
        )
        openai_tools = convert_anthropic_tools_to_openai(anthropic_request.tools)
        openai_tool_choice = convert_anthropic_tool_choice_to_openai(
            anthropic_request.tool_choice, request_id
        )
    except Exception as e:
        return await _log_and_return_error_response(
            request,
            500,
            AnthropicErrorType.API_ERROR,
            "Error during request conversion.",
            e,
        )

    # Build OpenAI-compatible request for Forge
    # Cap max_tokens to reasonable limits to avoid provider errors
    max_tokens = anthropic_request.max_tokens
    if max_tokens > 16384:  # GPT-4o and most models limit
        max_tokens = 16384
        logger.warning(
            f"max_tokens capped from {anthropic_request.max_tokens} to {max_tokens} to comply with model limits",
            extra={"request_id": request_id}
        )
    
    openai_payload = {
        "model": anthropic_request.model,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "stream": is_stream,
    }

    # Add optional parameters if present
    if anthropic_request.temperature is not None:
        openai_payload["temperature"] = anthropic_request.temperature
    if anthropic_request.top_p is not None:
        openai_payload["top_p"] = anthropic_request.top_p
    if anthropic_request.stop_sequences:
        openai_payload["stop"] = anthropic_request.stop_sequences
    if openai_tools:
        openai_payload["tools"] = openai_tools
    if openai_tool_choice:
        openai_payload["tool_choice"] = openai_tool_choice
    if anthropic_request.metadata and anthropic_request.metadata.get("user_id"):
        openai_payload["user"] = str(anthropic_request.metadata.get("user_id"))

    logger.debug(
        "Prepared OpenAI request parameters for Forge",
        extra={
            "request_id": request_id,
            "data": {"params": openai_payload},
        },
    )

    try:
        # Use Forge's provider service to process the request
        provider_service = await ProviderService.async_get_instance(user, db, api_key_id)
        allowed_provider_names = await _get_allowed_provider_names(request, db)

        # Process request through Forge
        response = await provider_service.process_request(
            "chat/completions", 
            openai_payload, 
            allowed_provider_names=allowed_provider_names
        )

        # Handle streaming response
        if inspect.isasyncgen(response):
            logger.debug(
                "Initiating streaming request to provider via Forge",
                extra={"request_id": request_id},
            )
            
            return StreamingResponse(
                handle_anthropic_streaming_response_from_openai_stream(
                    response,
                    anthropic_request.model,
                    estimated_input_tokens,
                    request_id,
                    request.state.start_time_monotonic,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        
        # Handle non-streaming response
        else:
            logger.debug(
                "Received provider response via Forge",
                extra={
                    "request_id": request_id,
                    "data": {"response": response},
                },
            )

            # Convert OpenAI response back to Anthropic format
            anthropic_response = convert_openai_to_anthropic_response(
                response, anthropic_request.model, request_id=request_id
            )

            duration_ms = (time.monotonic() - request.state.start_time_monotonic) * 1000
            logger.info(
                "Claude Code non-streaming request completed successfully",
                extra={
                    "request_id": request_id,
                    "data": {
                        "status_code": 200,
                        "duration_ms": duration_ms,
                        "input_tokens": anthropic_response.usage.input_tokens,
                        "output_tokens": anthropic_response.usage.output_tokens,
                        "stop_reason": anthropic_response.stop_reason,
                    },
                },
            )

            logger.debug(
                "Prepared Claude Code response",
                extra={
                    "request_id": request_id,
                    "data": {"response": anthropic_response.model_dump(exclude_unset=True)},
                },
            )

            return JSONResponse(
                content=anthropic_response.model_dump(exclude_unset=True)
            )

    except ValueError as e:
        return await _log_and_return_error_response(
            request,
            400,
            AnthropicErrorType.INVALID_REQUEST,
            str(e),
            e,
        )
    except Exception as e:
        # Handle provider API errors specifically
        from app.exceptions.exceptions import ProviderAPIException
        if isinstance(e, ProviderAPIException):
            return await _log_and_return_error_response(
                request,
                e.error_code,
                AnthropicErrorType.API_ERROR,
                f"Provider error: {e.error_message}",
                e,
            )
        
        # Log the actual exception details for debugging
        error_msg = str(e).replace("{", "{{").replace("}", "}}")  # Escape braces for logging
        logger.error(
            f"Detailed error in Claude Code processing: {type(e).__name__}: {error_msg}",
            extra={"request_id": request_id},
            exc_info=e,
        )
        return await _log_and_return_error_response(
            request,
            500,
            AnthropicErrorType.API_ERROR,
            f"An unexpected error occurred while processing the request: {str(e)}",
            e,
        )


@router.post(
    "/messages/count_tokens", 
    response_model=TokenCountResponse, 
    tags=["Claude Code Utility"]
)
async def count_tokens_endpoint(
    request: Request,
    user: User = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> TokenCountResponse:
    """Estimates token count for given Anthropic messages and system prompt."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time_mono = time.monotonic()

    try:
        body = await request.json()
        count_request = TokenCountRequest.model_validate(body)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON body.") from e
    except ValidationError as e:
        raise HTTPException(
            status_code=422, detail=f"Invalid request body: {str(e.errors())}"
        ) from e

    token_count = count_tokens_for_anthropic_request(
        messages=count_request.messages,
        system=count_request.system,
        model_name=count_request.model,
        tools=count_request.tools,
        request_id=request_id,
    )

    duration_ms = (time.monotonic() - start_time_mono) * 1000
    logger.info(
        f"Counted {token_count} tokens",
        extra={
            "request_id": request_id,
            "data": {
                "duration_ms": duration_ms,
                "token_count": token_count,
                "model": count_request.model,
            },
        },
    )

    return TokenCountResponse(input_tokens=token_count) 