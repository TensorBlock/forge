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

logger = get_logger(name="provider_keys")

router = APIRouter()

# --- Internal Service Functions ---


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

    encrypted_key = encrypt_api_key(provider_key_create.api_key)
    db_provider_key = ProviderKeyModel(
        user_id=current_user.id,
        provider_name=provider_key_create.provider_name,
        encrypted_api_key=encrypted_key,
        base_url=provider_key_create.base_url,
        model_mapping=provider_key_create.model_mapping,
    )
    db.add(db_provider_key)
    await db.commit()
    await db.refresh(db_provider_key)

    # Invalidate caches after creating a new provider key
    await invalidate_provider_service_cache_async(current_user.id)

    return ProviderKey.model_validate(db_provider_key)


async def _update_provider_key_internal(
    key_id: int,
    provider_key_update: ProviderKeyUpdate,
    db: AsyncSession,
    current_user: UserModel,
) -> ProviderKey:
    """
    Internal logic to update a provider key for the current user.
    """
    result = await db.execute(
        select(ProviderKeyModel).filter(
            ProviderKeyModel.id == key_id,
            ProviderKeyModel.user_id == current_user.id,
        )
    )
    db_provider_key = result.scalar_one_or_none()
    
    if not db_provider_key:
        raise HTTPException(status_code=404, detail="Provider key not found")

    update_data = provider_key_update.model_dump(exclude_unset=True)
    if "api_key" in update_data:
        update_data["encrypted_api_key"] = encrypt_api_key(update_data.pop("api_key"))

    for field, value in update_data.items():
        setattr(db_provider_key, field, value)

    await db.commit()
    await db.refresh(db_provider_key)

    # Invalidate caches after updating a provider key
    await invalidate_provider_service_cache_async(current_user.id)

    return ProviderKey.model_validate(db_provider_key)


async def _delete_provider_key_internal(
    key_id: int, db: AsyncSession, current_user: UserModel
) -> ProviderKey:
    """
    Internal logic to delete a provider key for the current user.
    """
    result = await db.execute(
        select(ProviderKeyModel).filter(
            ProviderKeyModel.id == key_id,
            ProviderKeyModel.user_id == current_user.id,
        )
    )
    db_provider_key = result.scalar_one_or_none()
    
    if not db_provider_key:
        raise HTTPException(status_code=404, detail="Provider key not found")

    # Store the provider key data before deletion
    provider_key_data = ProviderKey.model_validate(db_provider_key)

    await db.delete(db_provider_key)
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


@router.put("/{key_id}", response_model=ProviderKey)
async def update_provider_key(
    key_id: int,
    provider_key_update: ProviderKeyUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return await _update_provider_key_internal(
        key_id, provider_key_update, db, current_user
    )


@router.delete("/{key_id}", response_model=ProviderKey)
async def delete_provider_key(
    key_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return await _delete_provider_key_internal(key_id, db, current_user)


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


@router.put("/clerk/{key_id}", response_model=ProviderKey)
async def update_provider_key_clerk(
    key_id: int,
    provider_key_update: ProviderKeyUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return await _update_provider_key_internal(
        key_id, provider_key_update, db, current_user
    )


@router.delete("/clerk/{key_id}", response_model=ProviderKey)
async def delete_provider_key_clerk(
    key_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return await _delete_provider_key_internal(key_id, db, current_user)


# --- Batch Upsert API Endpoint ---


async def _batch_upsert_provider_keys_internal(
    items: list[ProviderKeyUpsertItem],
    db: AsyncSession,
    current_user: UserModel,
) -> list[ProviderKeyModel]:
    """
    Internal logic for batch creating or updating provider keys for the current user.
    """
    processed_keys: list[ProviderKeyModel] = []

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
            # Handle deletion if api_key is "DELETE"
            if item.api_key == "DELETE":
                try:
                    await _delete_provider_key_internal(item.provider_name, db, current_user)
                except HTTPException as e:
                    if (
                        e.status_code != status.HTTP_404_NOT_FOUND
                    ):  # Ignore 404 errors for missing keys
                        raise
                continue

            db_key_to_process: ProviderKeyModel | None = existing_keys_map.get(
                item.provider_name
            )

            if db_key_to_process:  # Update existing key
                try:
                    # try to initialize the provider adapter if key info is provided
                    provider_adapter_cls = ProviderAdapterFactory.get_adapter_cls(
                        item.provider_name
                    )
                    _, old_config = provider_adapter_cls.deserialize_api_key_config(
                        decrypt_api_key(db_key_to_process.encrypted_api_key)
                    )
                    if item.api_key or item.config:
                        serialized_api_key_config = (
                            provider_adapter_cls.serialize_api_key_config(
                                item.api_key, item.config
                            )
                        )
                        db_key_to_process.encrypted_api_key = encrypt_api_key(
                            serialized_api_key_config
                        )
                    if (
                        item.base_url is not None
                    ):  # Allows setting base_url to "" or null
                        db_key_to_process.base_url = item.base_url
                    if item.model_mapping is not None:
                        db_key_to_process.model_mapping = json.dumps(item.model_mapping)
                    elif (
                        hasattr(item, "model_mapping") and item.model_mapping is None
                    ):  # Explicitly clear if None
                        db_key_to_process.model_mapping = None
                    provider_adapter_cls(
                        item.provider_name,
                        db_key_to_process.base_url,
                        config=item.config or old_config,
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Error updating provider {item.provider_name}: {e}",
                    )
                # No need to db.add() as it's already tracked by the session
            else:  # Create new key
                if not item.api_key:
                    raise HTTPException(
                        status_code=400,
                        detail=f"api_key is required to create a new provider key for {item.provider_name}",
                    )
                model_mapping_json = (
                    json.dumps(item.model_mapping) if item.model_mapping else None
                )
                provider_adapter_cls = ProviderAdapterFactory.get_adapter_cls(
                    item.provider_name
                )
                # try to initialize the provider adapter
                try:
                    provider_adapter_cls(
                        item.provider_name, item.base_url, config=item.config
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Error initializing provider {item.provider_name}: {e}",
                    )
                serialized_api_key_config = (
                    provider_adapter_cls.serialize_api_key_config(
                        item.api_key, item.config
                    )
                )
                db_key_to_process = ProviderKeyModel(
                    provider_name=item.provider_name,
                    encrypted_api_key=encrypt_api_key(serialized_api_key_config),
                    user_id=current_user.id,
                    base_url=item.base_url,
                    model_mapping=model_mapping_json,
                )
                db.add(db_key_to_process)

            processed_keys.append(db_key_to_process)

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

    if processed_keys:
        try:
            await db.commit()
            for key in processed_keys:
                await db.refresh(
                    key
                )  # Refresh each key to get DB-generated values like id, timestamps
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
