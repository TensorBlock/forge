import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.api.dependencies import (
    get_current_active_user,
    get_current_active_user_from_clerk,
)
from app.api.schemas.provider_key import (
    ProviderKey,
    ProviderKeyCreate,
    ProviderKeyUpdate,
    ProviderKeyUpsertItem,
)
from app.core.async_cache import invalidate_provider_service_cache_async
from app.core.database import get_async_db
from app.core.logger import get_logger
from app.core.security import decrypt_api_key, encrypt_api_key
from app.models.provider_key import ProviderKey as ProviderKeyModel
from app.models.user import User as UserModel
from app.services.providers.adapter_factory import ProviderAdapterFactory
from app.services.providers.base import ProviderAdapter

logger = get_logger(name="provider_keys")

router = APIRouter()

# --- Internal Service Functions ---

def _validate_provider_cls_init(provider_name: str, base_url: str, config: dict[str, Any]) -> ProviderAdapter:
    provider_cls = ProviderAdapterFactory.get_adapter_cls(provider_name)
    try:
        provider_cls(provider_name, base_url, config=config)
    except Exception as e:
        logger.error({
            "message": f"Error initializing provider {provider_name}",
            "extra":{
                "error": str(e),
            }
        })
        raise HTTPException(
            status_code=400,
            detail=f"Error initializing provider {provider_name}",
        )
    return provider_cls


async def _get_provider_keys_internal(
    db: AsyncSession, current_user: UserModel
) -> list[ProviderKey]:
    """
    Internal logic to get all provider keys for the current user.
    """
    result = await db.execute(
        select(ProviderKeyModel).filter(ProviderKeyModel.user_id == current_user.id)
    )
    provider_keys = result.scalars().all()
    return [ProviderKey.model_validate(pk) for pk in provider_keys]


async def _process_provider_key_create_data(
    db: AsyncSession,
    provider_key_create: ProviderKeyCreate,
    user_id: int,
) -> ProviderKeyModel:
    provider_name = provider_key_create.provider_name
    provider_cls = _validate_provider_cls_init(provider_name, provider_key_create.base_url, provider_key_create.config)
    serialized_api_key_config = provider_cls.serialize_api_key_config(provider_key_create.api_key, provider_key_create.config)

    encrypted_key = encrypt_api_key(serialized_api_key_config)
    db_provider_key = ProviderKeyModel(
        user_id=user_id,
        provider_name=provider_name,
        encrypted_api_key=encrypted_key,
        base_url=provider_key_create.base_url,
        model_mapping=provider_key_create.model_mapping,
    )
    db.add(db_provider_key)
    return db_provider_key


async def _create_provider_key_internal(
    provider_key_create: ProviderKeyCreate, db: AsyncSession, current_user: UserModel
) -> ProviderKey:
    """
    Internal logic to create a new provider key for the current user.
    """
    # Check if provider already exists for user
    result = await db.execute(
        select(ProviderKeyModel).filter(
            ProviderKeyModel.user_id == current_user.id,
            ProviderKeyModel.provider_name == provider_key_create.provider_name,
        )
    )
    existing_key = result.scalar_one_or_none()
    
    if existing_key:
        raise HTTPException(
            status_code=400,
            detail=f"Provider key for {provider_key_create.provider_name} already exists",
        )
    
    db_provider_key = await _process_provider_key_create_data(db, provider_key_create, current_user.id)
    await db.commit()
    await db.refresh(db_provider_key)

    # Invalidate caches after creating a new provider key
    await invalidate_provider_service_cache_async(current_user.id)

    return ProviderKey.model_validate(db_provider_key)


async def _process_provider_key_update_data(
    db_provider_key: ProviderKeyModel,
    provider_key_update: ProviderKeyUpdate,
) -> ProviderKeyModel:
    update_data = provider_key_update.model_dump(exclude_unset=True)
    provider_cls = ProviderAdapterFactory.get_adapter_cls(db_provider_key.provider_name)
    old_api_key, old_config = provider_cls.deserialize_api_key_config(decrypt_api_key(db_provider_key.encrypted_api_key))

    if "api_key" in update_data or "config" in update_data:
        api_key = update_data.pop("api_key", None) or old_api_key
        config = update_data.pop("config", None) or old_config
        _validate_provider_cls_init(db_provider_key.provider_name, db_provider_key.base_url, config)
        serialized_api_key_config = provider_cls.serialize_api_key_config(api_key, config)
        update_data['encrypted_api_key'] = encrypt_api_key(serialized_api_key_config)

    for field, value in update_data.items():
        setattr(db_provider_key, field, value)

    return db_provider_key


async def _update_provider_key_internal(
    provider_name: str,
    provider_key_update: ProviderKeyUpdate,
    db: AsyncSession,
    current_user: UserModel,
) -> ProviderKey:
    """
    Internal logic to update a provider key for the current user.
    """
    result = await db.execute(
        select(ProviderKeyModel).filter(
            ProviderKeyModel.provider_name == provider_name,
            ProviderKeyModel.user_id == current_user.id,
        )
    )
    db_provider_key = result.scalar_one_or_none()
    
    if not db_provider_key:
        raise HTTPException(status_code=404, detail="Provider key not found")
    
    db_provider_key = await _process_provider_key_update_data(db_provider_key, provider_key_update)

    await db.commit()
    await db.refresh(db_provider_key)

    # Invalidate caches after updating a provider key
    await invalidate_provider_service_cache_async(current_user.id)

    return ProviderKey.model_validate(db_provider_key)


async def _process_provider_key_delete_data(
    db: AsyncSession,
    provider_name: str,
    user_id: int,
) -> ProviderKeyModel:
    result = await db.execute(
        select(ProviderKeyModel).filter(
            ProviderKeyModel.provider_name == provider_name,
            ProviderKeyModel.user_id == user_id,
        )
    )
    db_provider_key = result.scalar_one_or_none()
    
    if not db_provider_key:
        raise HTTPException(status_code=404, detail="Provider key not found")

    # Store the provider key data before deletion
    provider_key_data = ProviderKey.model_validate(db_provider_key)

    await db.delete(db_provider_key)

    return provider_key_data


async def _delete_provider_key_internal(
    provider_name: str, db: AsyncSession, current_user: UserModel
) -> ProviderKey:
    """
    Internal logic to delete a provider key for the current user.
    """
    provider_key_data = await _process_provider_key_delete_data(db, provider_name, current_user.id)
    await db.commit()

    # Invalidate caches after deleting a provider key
    await invalidate_provider_service_cache_async(current_user.id)

    return provider_key_data

# --- API Endpoints ---


@router.get("/", response_model=list[ProviderKey])
async def get_provider_keys(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return await _get_provider_keys_internal(db, current_user)


@router.post("/", response_model=ProviderKey)
async def create_provider_key(
    provider_key_create: ProviderKeyCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return await _create_provider_key_internal(provider_key_create, db, current_user)


@router.put("/{provider_name}", response_model=ProviderKey)
async def update_provider_key(
    provider_name: str,
    provider_key_update: ProviderKeyUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return await _update_provider_key_internal(
        provider_name, provider_key_update, db, current_user
    )


@router.delete("/{provider_name}", response_model=ProviderKey)
async def delete_provider_key(
    provider_name: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return await _delete_provider_key_internal(provider_name, db, current_user)


# --- Clerk API Routes ---


@router.get("/clerk", response_model=list[ProviderKey])
async def get_provider_keys_clerk(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return await _get_provider_keys_internal(db, current_user)


@router.post("/clerk", response_model=ProviderKey)
async def create_provider_key_clerk(
    provider_key_create: ProviderKeyCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return await _create_provider_key_internal(provider_key_create, db, current_user)


@router.put("/clerk/{provider_name}", response_model=ProviderKey)
async def update_provider_key_clerk(
    provider_name: str,
    provider_key_update: ProviderKeyUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return await _update_provider_key_internal(
        provider_name, provider_key_update, db, current_user
    )


@router.delete("/clerk/{provider_name}", response_model=ProviderKey)
async def delete_provider_key_clerk(
    provider_name: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return await _delete_provider_key_internal(provider_name, db, current_user)


# --- Batch Upsert API Endpoint ---


async def _batch_upsert_provider_keys_internal(
    items: list[ProviderKeyUpsertItem],
    db: AsyncSession,
    current_user: UserModel,
) -> list[ProviderKey]:
    """
    Internal logic for batch creating or updating provider keys for the current user.
    """
    processed_keys: list[ProviderKeyModel] = []
    processed: bool = False

    # 1. Fetch all existing keys for the user
    result = await db.execute(
        select(ProviderKeyModel).filter(ProviderKeyModel.user_id == current_user.id)
    )
    existing_keys_query = result.scalars().all()
    # 2. Map them by provider_name for efficient lookup
    existing_keys_map: dict[str, ProviderKeyModel] = {
        key.provider_name: key for key in existing_keys_query
    }

    for item in items:
        if "****" in item.api_key:
            continue

        try:
            existing_provider_key: ProviderKeyModel | None = existing_keys_map.get(item.provider_name)

            # Handle deletion if api_key is "DELETE"
            if item.api_key == "DELETE":
                if existing_provider_key:
                    await _process_provider_key_delete_data(db, item.provider_name, current_user.id)
                    processed = True
            elif existing_provider_key:  # Update existing key
                db_key_to_process = await _process_provider_key_update_data(existing_provider_key, ProviderKeyUpdate.model_validate(item.model_dump(exclude_unset=True)))
                processed_keys.append(db_key_to_process)
                processed = True
            else:  # Create new key
                db_key_to_process = await _process_provider_key_create_data(db, ProviderKeyCreate.model_validate(item.model_dump(exclude_unset=True)), current_user.id)
                processed_keys.append(db_key_to_process)
                processed = True

        except HTTPException as http_exc:
            # db.rollback() # Optional: rollback if any item fails, or handle partial success
            raise HTTPException(
                status_code=http_exc.status_code,
                detail=f"Error processing '{item.provider_name}': {http_exc.detail}",
            )
        except Exception as e:
            # db.rollback()
            error_message_prefix = (
                f"Unexpected error during batch upsert for {item.provider_name}"
            )
            if hasattr(current_user, "email"):  # Check if it's a full User object
                error_message_prefix += f" (User: {current_user.email})"
            logger.error(f"{error_message_prefix}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred while processing '{item.provider_name}'.",
            )

    if processed:
        try:
            await db.commit()
            for key in processed_keys:
                await db.refresh(key)  # Refresh each key to get DB-generated values like id, timestamps
            processed_keys = [ProviderKey.model_validate(key) for key in processed_keys]
            await invalidate_provider_service_cache_async(current_user.id)
        except Exception as e:
            await db.rollback()
            error_message_prefix = "Error during final commit/refresh in batch upsert"
            if hasattr(current_user, "email"):  # Check if it's a full User object
                error_message_prefix += f" (User: {current_user.email})"
            logger.error(f"{error_message_prefix}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to save changes to the database."
            )

    return processed_keys


@router.post("/batch-upsert", response_model=list[ProviderKey])
async def batch_upsert_provider_keys(
    items: list[ProviderKeyUpsertItem],
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    """
    Batch create or update provider keys for the current user.
    """
    return await _batch_upsert_provider_keys_internal(items, db, current_user)


@router.post("/clerk/batch-upsert", response_model=list[ProviderKey])
async def batch_upsert_provider_keys_clerk(
    items: list[ProviderKeyUpsertItem],
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    """
    Batch create or update provider keys for the current user (Clerk authenticated).
    """
    return await _batch_upsert_provider_keys_internal(items, db, current_user)
