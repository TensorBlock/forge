from typing import AsyncGenerator
import json
from fastapi import HTTPException
from starlette.responses import StreamingResponse
from app.exceptions.exceptions import ProviderAPIException

async def wrap_streaming_response_with_error_handling(
    logger, async_gen: AsyncGenerator[bytes, None] 
) -> StreamingResponse:
    """
    Wraps an async generator to catch and properly handle errors in streaming responses.
    Returns a StreamingResponse that will:
    - Return proper HTTP error status if error occurs before first chunk
    - Send error as SSE event if error occurs mid-stream
    
    Args:
        logger: Logger instance for error logging
        async_gen: The async generator producing the stream chunks
        
    Returns:
        StreamingResponse with proper error handling
        
    Raises:
        HTTPException: If error occurs before streaming starts
    """
    
    # Try to get the first chunk BEFORE creating StreamingResponse
    # This allows us to catch immediate errors and return proper HTTP status
    try:
        first_chunk = await async_gen.__anext__()
    except StopAsyncIteration:
        # Empty stream
        logger.error("Empty stream response")
        raise HTTPException(status_code=500, detail="Empty stream response")
    except ProviderAPIException as e:
        logger.error(f"Provider API error: {str(e)}")
        raise HTTPException(status_code=e.error_code, detail=e.error_message) from e
    except Exception as e:
        # Convert other exceptions to HTTPException
        logger.error(f"Error before streaming started: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    
    # Success! Now create generator that replays first chunk + rest
    async def response_generator():
        # Yield the first chunk we already got
        yield first_chunk
        
        try:
            # Continue with the rest of the stream
            async for chunk in async_gen:
                yield chunk
        except Exception as e:
            # Error occurred mid-stream - HTTP status already sent
            # Send error as SSE event to inform the client
            logger.error(f"Error during streaming: {str(e)}")
            
            error_message = str(e)
            error_event = {
                "error": {
                    "message": error_message,
                    "type": "stream_error",
                    "code": "provider_error"
                }
            }
            yield f"data: {json.dumps(error_event)}\n\n".encode()

            # Send [DONE] to properly close the stream
            yield b"data: [DONE]\n\n"
    
    # Set appropriate headers for streaming
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Prevent Nginx buffering
    }
    
    return StreamingResponse(
        response_generator(), 
        media_type="text/event-stream", 
        headers=headers
    )