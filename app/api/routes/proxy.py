import inspect
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import StreamingResponse

from app.api.dependencies import get_user_by_api_key
from app.api.schemas.openai import (
    ChatCompletionRequest,
    CompletionRequest,
    CompletionResponse,
    EmbeddingsRequest,
    ImageEditsRequest,
    ImageGenerationRequest,
)
from app.core.async_cache import async_provider_service_cache
from app.core.database import get_async_db
from app.core.logger import get_logger
from app.models.forge_api_key import ForgeApiKey
from app.models.user import User
from app.services.provider_service import ProviderService

router = APIRouter()
logger = get_logger(name="proxy")


# -------------------------------------------------------------
# Helper: return the provider-scope allowed for the current Forge API key.
# None → unrestricted, [] → explicitly no providers.
# -------------------------------------------------------------
async def _get_allowed_provider_names(
    request: Request, db: AsyncSession
) -> list[str] | None:
    api_key = getattr(request.state, "forge_api_key", None)
    if api_key is None:
        from app.api.dependencies import get_api_key_from_headers

        api_key = await get_api_key_from_headers(request)
        # Remove the forge- prefix for caching from the API key
        api_key = api_key[6:]

    allowed = getattr(request.state, "allowed_provider_names", None)
    if allowed is not None:
        return allowed

    allowed = await async_provider_service_cache.get(f"forge_scope:{api_key}")

    if allowed is None:
        result = await db.execute(
            select(ForgeApiKey)
            .options(selectinload(ForgeApiKey.allowed_provider_keys))
            .filter(ForgeApiKey.key == f"forge-{api_key}", ForgeApiKey.is_active)
        )
        forge_key = result.scalar_one_or_none()
        if forge_key is None:
            raise HTTPException(
                status_code=401, detail="Forge API key not found or inactive"
            )
        allowed = [pk.provider_name for pk in forge_key.allowed_provider_keys]
        await async_provider_service_cache.set(
            f"forge_scope:{api_key}", allowed, ttl=300
        )

    request.state.allowed_provider_names = allowed
    return allowed


@router.post("/chat/completions")
async def create_chat_completion(
    request: Request,
    chat_request: ChatCompletionRequest,
    user: User = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """
    Create a chat completion (OpenAI-compatible endpoint).
    """
    try:
        # Get cached provider service instance
        provider_service = await ProviderService.async_get_instance(user, db)

        # Convert to dict and extract request properties
        payload = chat_request.dict(exclude_unset=True)

        # Get allowed provider names for the current request
        allowed_provider_names = await _get_allowed_provider_names(request, db)

        # Get the response from the provider
        response = await provider_service.process_request(
            "chat/completions", payload, allowed_provider_names=allowed_provider_names
        )

        # Check if it's a streaming response by checking if it's an async generator
        if inspect.isasyncgen(response):
            # Set appropriate headers for streaming
            headers = {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Prevent Nginx buffering
            }

            return StreamingResponse(
                response, media_type="text/event-stream", headers=headers
            )

        # Otherwise, return the JSON response directly
        return response
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(err)}"
        ) from err


@router.post("/completions", response_model=CompletionResponse)
async def create_completion(
    request: Request,
    completion_request: CompletionRequest,
    user: User = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """
    Create a completion (OpenAI-compatible endpoint).
    """
    try:
        provider_service = await ProviderService.async_get_instance(user, db)
        allowed_provider_names = await _get_allowed_provider_names(request, db)

        response = await provider_service.process_request(
            "completions",
            completion_request.dict(exclude_unset=True),
            allowed_provider_names=allowed_provider_names,
        )

        # Check if it's a streaming response
        if inspect.isasyncgen(response):
            headers = {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Prevent Nginx buffering
            }

            return StreamingResponse(
                response, media_type="text/event-stream", headers=headers
            )

        # Otherwise, return the JSON response directly
        return response
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(err)}"
        ) from err


@router.post("/images/generations")
async def create_image_generation(
    request: Request,
    image_generation_request: ImageGenerationRequest,
    user: User = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """
    Create an image generation (OpenAI-compatible endpoint).
    """
    try:
        provider_service = await ProviderService.async_get_instance(user, db)

        payload = image_generation_request.model_dump(mode="json", exclude_unset=True)

        allowed_provider_names = await _get_allowed_provider_names(request, db)
        response = await provider_service.process_request(
            "images/generations",
            payload,
            allowed_provider_names=allowed_provider_names,
        )

        return response
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(err)}"
        ) from err


@router.post("/images/edits")
async def create_image_edits(
    request: Request,
    image_edits_request: ImageEditsRequest,
    user: User = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    try:
        provider_service = await ProviderService.async_get_instance(user, db)
        payload = image_edits_request.model_dump(mode="json", exclude_unset=True)
        allowed_provider_names = await _get_allowed_provider_names(request, db)
        response = await provider_service.process_request(
            "images/edits",
            payload,
            allowed_provider_names=allowed_provider_names,
        )
        return response
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(err)}"
        ) from err


@router.get("/models")
async def list_models(
    request: Request,
    user: User = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """
    List available models. Only models from providers that are within the scope of the
    Forge API key used for this request are returned.
    """
    try:
        # Determine allowed providers via helper (shared with other endpoints)
        allowed_provider_names = await _get_allowed_provider_names(request, db)

        provider_service = await ProviderService.async_get_instance(user, db)
        models = await provider_service.list_models(
            allowed_provider_names=allowed_provider_names
        )
        return {"object": "list", "data": models}
    except Exception as err:
        logger.error(f"Error listing models: {str(err)}")
        raise HTTPException(
            status_code=500, detail=f"Error listing models: {str(err)}"
        ) from err



@router.post("/embeddings")
async def create_embeddings(
    request: Request,
    embeddings_request: EmbeddingsRequest,
    user: User = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """
    Create embeddings (OpenAI-compatible endpoint).
    """
    try:
        provider_service = await ProviderService.async_get_instance(user, db)
        payload = embeddings_request.model_dump(mode="json", exclude_unset=True)
        allowed_provider_names = await _get_allowed_provider_names(request, db)
        response = await provider_service.process_request(
            "embeddings",
            payload,
            allowed_provider_names=allowed_provider_names,
        )
        return response
    except NotImplementedError as err:
        raise HTTPException(
            status_code=404, detail=f"Error processing request: {str(err)}"
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(err)}"
        ) from err
