import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
from app.core.cache import invalidate_provider_service_cache
from app.core.database import get_db
from app.core.logger import get_logger
from app.core.security import decrypt_api_key, encrypt_api_key
from app.models.provider_key import ProviderKey as ProviderKeyModel
from app.models.user import User
from app.services.providers.adapter_factory import ProviderAdapterFactory

logger = get_logger(name="provider_keys")

router = APIRouter()

# --- Internal Service Functions ---


def _get_provider_keys_internal(
    db: Session, current_user: User
) -> list[ProviderKeyModel]:
    """Internal. Retrieve all provider keys for the current user."""
    return (
        db.query(ProviderKeyModel)
        .filter(ProviderKeyModel.user_id == current_user.id)
        .all()
    )


def _create_provider_key_internal(
    provider_key_in: ProviderKeyCreate, db: Session, current_user: User
) -> ProviderKeyModel:
    """Internal. Create a new provider key."""
    existing_key = (
        db.query(ProviderKeyModel)
        .filter(
            ProviderKeyModel.user_id == current_user.id,
            ProviderKeyModel.provider_name == provider_key_in.provider_name,
        )
        .first()
    )
    if existing_key:
        raise HTTPException(
            status_code=400,
            detail=f"A key for provider {provider_key_in.provider_name} already exists",
        )

    model_mapping_json = (
        json.dumps(provider_key_in.model_mapping)
        if provider_key_in.model_mapping
        else None
    )

    provider_name = provider_key_in.provider_name
    provider_adapter_cls = ProviderAdapterFactory.get_adapter_cls(provider_name)

    # try to initialize the provider adapter
    try:
        provider_adapter_cls(
            provider_name, provider_key_in.base_url, config=provider_key_in.config
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error initializing provider {provider_name}: {e}",
        )

    serialized_api_key_config = provider_adapter_cls.serialize_api_key_config(
        provider_key_in.api_key, provider_key_in.config
    )

    provider_key = ProviderKeyModel(
        provider_name=provider_name,
        encrypted_api_key=encrypt_api_key(serialized_api_key_config),
        user_id=current_user.id,
        base_url=provider_key_in.base_url,
        model_mapping=model_mapping_json,
    )
    db.add(provider_key)
    db.commit()
    db.refresh(provider_key)
    invalidate_provider_service_cache(current_user.id)
    return provider_key


def _update_provider_key_internal(
    provider_name: str,
    provider_key_in: ProviderKeyUpdate,
    db: Session,
    current_user: User,
) -> ProviderKeyModel:
    """Internal. Update a provider key."""
    provider_key = (
        db.query(ProviderKeyModel)
        .filter(
            ProviderKeyModel.user_id == current_user.id,
            ProviderKeyModel.provider_name == provider_name,
        )
        .first()
    )
    if not provider_key:
        raise HTTPException(
            status_code=404,
            detail=f"Provider key for {provider_name} not found",
        )

    # try to initialize the provider adapter if key info is provided
    try:
        provider_adapter_cls = ProviderAdapterFactory.get_adapter_cls(provider_name)
        _, old_config = provider_adapter_cls.deserialize_api_key_config(
            decrypt_api_key(provider_key.encrypted_api_key)
        )
        if provider_key_in.api_key or provider_key_in.config:
            serialized_api_key_config = provider_adapter_cls.serialize_api_key_config(
                provider_key_in.api_key, provider_key_in.config
            )
            provider_key.encrypted_api_key = encrypt_api_key(serialized_api_key_config)
        if provider_key_in.base_url is not None:
            provider_key.base_url = provider_key_in.base_url
        if provider_key_in.model_mapping is not None:
            provider_key.model_mapping = json.dumps(provider_key_in.model_mapping)

        provider_adapter_cls(
            provider_name,
            provider_key.base_url,
            config=provider_key_in.config or old_config,
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error initializing provider {provider_name}: {e}",
        )

    db.commit()
    db.refresh(provider_key)
    invalidate_provider_service_cache(current_user.id)
    return provider_key


def _delete_provider_key_internal(
    provider_name: str, db: Session, current_user: User
) -> ProviderKeyModel:
    """Internal. Delete a provider key."""
    provider_key = (
        db.query(ProviderKeyModel)
        .filter(
            ProviderKeyModel.user_id == current_user.id,
            ProviderKeyModel.provider_name == provider_name,
        )
        .first()
    )
    if not provider_key:
        raise HTTPException(
            status_code=404,
            detail=f"Provider key for {provider_name} not found",
        )
    db.delete(provider_key)
    db.commit()
    invalidate_provider_service_cache(current_user.id)
    return provider_key


@router.get("/", response_model=list[ProviderKey])
def get_provider_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    return _get_provider_keys_internal(db, current_user)


@router.post("/", response_model=ProviderKey)
def create_provider_key(
    provider_key_in: ProviderKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    return _create_provider_key_internal(provider_key_in, db, current_user)


@router.put("/{provider_name}", response_model=ProviderKey)
def update_provider_key(
    provider_name: str,
    provider_key_in: ProviderKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    return _update_provider_key_internal(
        provider_name, provider_key_in, db, current_user
    )


@router.delete("/{provider_name}", response_model=ProviderKey)
def delete_provider_key(
    provider_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    return _delete_provider_key_internal(provider_name, db, current_user)


# Clerk versions of the routes
@router.get("/clerk", response_model=list[ProviderKey])
def get_provider_keys_clerk(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _get_provider_keys_internal(db, current_user)


@router.post("/clerk", response_model=ProviderKey)
def create_provider_key_clerk(
    provider_key_in: ProviderKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _create_provider_key_internal(provider_key_in, db, current_user)


@router.put("/clerk/{provider_name}", response_model=ProviderKey)
def update_provider_key_clerk(
    provider_name: str,
    provider_key_in: ProviderKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _update_provider_key_internal(
        provider_name, provider_key_in, db, current_user
    )


@router.delete("/clerk/{provider_name}", response_model=ProviderKey)
def delete_provider_key_clerk(
    provider_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _delete_provider_key_internal(provider_name, db, current_user)


# --- Batch Upsert API Endpoint ---


def _batch_upsert_provider_keys_internal(
    items: list[ProviderKeyUpsertItem],
    db: Session,
    current_user: User,
) -> list[ProviderKeyModel]:
    """
    Internal logic for batch creating or updating provider keys for the current user.
    """
    processed_keys: list[ProviderKeyModel] = []

    # 1. Fetch all existing keys for the user
    existing_keys_query = (
        db.query(ProviderKeyModel)
        .filter(ProviderKeyModel.user_id == current_user.id)
        .all()
    )
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
                    _delete_provider_key_internal(item.provider_name, db, current_user)
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
            db.commit()
            for key in processed_keys:
                db.refresh(
                    key
                )  # Refresh each key to get DB-generated values like id, timestamps
            invalidate_provider_service_cache(current_user.id)
        except Exception as e:
            db.rollback()
            error_message_prefix = "Error during final commit/refresh in batch upsert"
            if hasattr(current_user, "email"):  # Check if it's a full User object
                error_message_prefix += f" (User: {current_user.email})"
            logger.error(f"{error_message_prefix}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to save changes to the database."
            )

    return processed_keys


@router.post("/batch-upsert", response_model=list[ProviderKey])
def batch_upsert_provider_keys(
    items: list[ProviderKeyUpsertItem],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Batch create or update provider keys for the current user.
    """
    return _batch_upsert_provider_keys_internal(items, db, current_user)


@router.post("/clerk/batch-upsert", response_model=list[ProviderKey])
def batch_upsert_provider_keys_clerk(
    items: list[ProviderKeyUpsertItem],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_from_clerk),
) -> Any:
    """
    Batch create or update provider keys for the current user (Clerk authenticated).
    """
    return _batch_upsert_provider_keys_internal(items, db, current_user)
