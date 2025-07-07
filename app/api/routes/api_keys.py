from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_active_user,
    get_current_active_user_from_clerk,
)
from app.api.schemas.forge_api_key import (
    ForgeApiKeyCreate,
    ForgeApiKeyMasked,
    ForgeApiKeyResponse,
    ForgeApiKeyUpdate,
)
from app.core.cache import invalidate_provider_service_cache, invalidate_user_cache
from app.core.database import get_db
from app.core.security import generate_forge_api_key
from app.models.forge_api_key import ForgeApiKey
from app.models.provider_key import ProviderKey as ProviderKeyModel
from app.models.user import User as UserModel

router = APIRouter()

# --- Internal Service Functions ---


def _get_api_keys_internal(
    db: Session, current_user: UserModel
) -> list[ForgeApiKeyMasked]:
    """
    Internal logic to get all API keys for the current user.
    """
    api_keys_query = db.query(ForgeApiKey).filter(
        ForgeApiKey.user_id == current_user.id
    )
    api_keys = api_keys_query.all()

    masked_keys = []
    for api_key_db in api_keys:
        key_data = api_key_db.__dict__.copy()
        key_data["key"] = ForgeApiKeyMasked.mask_api_key(api_key_db.key)
        key_data["allowed_provider_key_ids"] = [
            pk.id for pk in api_key_db.allowed_provider_keys
        ]
        masked_keys.append(ForgeApiKeyMasked(**key_data))
    return masked_keys


def _create_api_key_internal(
    api_key_create: ForgeApiKeyCreate, db: Session, current_user: UserModel
) -> ForgeApiKeyResponse:
    """
    Internal logic to create a new API key for the current user.
    """
    new_key_value = generate_forge_api_key()
    db_api_key = ForgeApiKey(
        key=new_key_value,
        name=api_key_create.name,
        user_id=current_user.id,
    )

    if api_key_create.allowed_provider_key_ids is not None:
        allowed_providers = []
        if api_key_create.allowed_provider_key_ids:
            allowed_providers = (
                db.query(ProviderKeyModel)
                .filter(
                    ProviderKeyModel.id.in_(api_key_create.allowed_provider_key_ids),
                    ProviderKeyModel.user_id == current_user.id,
                )
                .all()
            )
            if len(allowed_providers) != len(
                set(api_key_create.allowed_provider_key_ids)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="One or more provider_key_ids are invalid or do not belong to the user.",
                )
        db_api_key.allowed_provider_keys = allowed_providers

    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)

    response_data = db_api_key.__dict__.copy()
    response_data["allowed_provider_key_ids"] = [
        pk.id for pk in db_api_key.allowed_provider_keys
    ]
    return ForgeApiKeyResponse(**response_data)


def _update_api_key_internal(
    key_id: int, api_key_update: ForgeApiKeyUpdate, db: Session, current_user: UserModel
) -> ForgeApiKeyResponse:
    """
    Internal logic to update an API key for the current user.
    """
    db_api_key = (
        db.query(ForgeApiKey)
        .filter(ForgeApiKey.id == key_id, ForgeApiKey.user_id == current_user.id)
        .first()
    )
    if not db_api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    update_data = api_key_update.model_dump(exclude_unset=True)
    if "name" in update_data:
        db_api_key.name = update_data["name"]
    if "is_active" in update_data:
        old_active_state = db_api_key.is_active
        db_api_key.is_active = update_data["is_active"]
        if old_active_state and not db_api_key.is_active:
            invalidate_user_cache(db_api_key.key)

    if api_key_update.allowed_provider_key_ids is not None:
        db_api_key.allowed_provider_keys.clear()
        if api_key_update.allowed_provider_key_ids:
            allowed_providers = (
                db.query(ProviderKeyModel)
                .filter(
                    ProviderKeyModel.id.in_(api_key_update.allowed_provider_key_ids),
                    ProviderKeyModel.user_id == current_user.id,
                )
                .all()
            )
            if len(allowed_providers) != len(
                set(api_key_update.allowed_provider_key_ids)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="One or more updated provider_key_ids are invalid or do not belong to the user.",
                )
            db_api_key.allowed_provider_keys.extend(allowed_providers)

    db.commit()
    db.refresh(db_api_key)

    response_data = db_api_key.__dict__.copy()
    response_data["allowed_provider_key_ids"] = [
        pk.id for pk in db_api_key.allowed_provider_keys
    ]
    return ForgeApiKeyResponse(**response_data)


def _delete_api_key_internal(
    key_id: int, db: Session, current_user: UserModel
) -> ForgeApiKeyResponse:
    """
    Internal logic to delete an API key for the current user.
    """
    db_api_key = (
        db.query(ForgeApiKey)
        .filter(ForgeApiKey.id == key_id, ForgeApiKey.user_id == current_user.id)
        .first()
    )
    if not db_api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    key_to_invalidate = db_api_key.key
    # Capture details for response before potential lazy-load issues after delete
    response_data = {
        "id": db_api_key.id,
        "key": key_to_invalidate,  # Or masked version if preferred
        "name": db_api_key.name,
        "is_active": db_api_key.is_active,
        "created_at": db_api_key.created_at,
        "last_used_at": db_api_key.last_used_at,
        "allowed_provider_key_ids": [pk.id for pk in db_api_key.allowed_provider_keys],
    }

    db.delete(db_api_key)
    db.commit()

    invalidate_user_cache(key_to_invalidate)
    invalidate_provider_service_cache(current_user.id)
    return ForgeApiKeyResponse(**response_data)


def _regenerate_api_key_internal(
    key_id: int, db: Session, current_user: UserModel
) -> ForgeApiKeyResponse:
    """
    Internal logic to regenerate an API key for the current user while preserving other settings.
    """
    db_api_key = (
        db.query(ForgeApiKey)
        .filter(ForgeApiKey.id == key_id, ForgeApiKey.user_id == current_user.id)
        .first()
    )
    if not db_api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Invalidate caches for the old key
    old_key = db_api_key.key
    invalidate_user_cache(old_key)
    invalidate_provider_service_cache(current_user.id)

    # Generate and set new key
    new_key_value = generate_forge_api_key()
    db_api_key.key = new_key_value

    db.commit()
    db.refresh(db_api_key)

    response_data = db_api_key.__dict__.copy()
    response_data["allowed_provider_key_ids"] = [
        pk.id for pk in db_api_key.allowed_provider_keys
    ]
    return ForgeApiKeyResponse(**response_data)


# --- API Endpoints ---


@router.get("/", response_model=list[ForgeApiKeyMasked])
def get_api_keys(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return _get_api_keys_internal(db, current_user)


@router.post("/", response_model=ForgeApiKeyResponse)
def create_api_key(
    api_key_create: ForgeApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return _create_api_key_internal(api_key_create, db, current_user)


@router.put("/{key_id}", response_model=ForgeApiKeyResponse)
def update_api_key(
    key_id: int,
    api_key_update: ForgeApiKeyUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return _update_api_key_internal(key_id, api_key_update, db, current_user)


@router.delete("/{key_id}", response_model=ForgeApiKeyResponse)
def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return _delete_api_key_internal(key_id, db, current_user)


@router.post("/{key_id}/regenerate", response_model=ForgeApiKeyResponse)
def regenerate_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    return _regenerate_api_key_internal(key_id, db, current_user)


# Clerk versions of the routes
@router.get("/clerk", response_model=list[ForgeApiKeyMasked])
def get_api_keys_clerk(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _get_api_keys_internal(db, current_user)


@router.post("/clerk", response_model=ForgeApiKeyResponse)
def create_api_key_clerk(
    api_key_create: ForgeApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _create_api_key_internal(api_key_create, db, current_user)


@router.put("/clerk/{key_id}", response_model=ForgeApiKeyResponse)
def update_api_key_clerk(
    key_id: int,
    api_key_update: ForgeApiKeyUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _update_api_key_internal(key_id, api_key_update, db, current_user)


@router.delete("/clerk/{key_id}", response_model=ForgeApiKeyResponse)
def delete_api_key_clerk(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _delete_api_key_internal(key_id, db, current_user)


@router.post("/clerk/{key_id}/regenerate", response_model=ForgeApiKeyResponse)
def regenerate_api_key_clerk(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    return _regenerate_api_key_internal(key_id, db, current_user)
