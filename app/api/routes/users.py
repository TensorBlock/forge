from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_active_user,
    get_current_active_user_from_clerk,
)
from app.api.schemas.user import MaskedUser, User, UserCreate, UserUpdate
from app.core.cache import invalidate_user_cache
from app.core.database import get_db
from app.core.logger import get_logger
from app.core.security import get_password_hash
from app.models.user import User as UserModel
from app.services.provider_service import create_default_tensorblock_provider_for_user

logger = get_logger(name="users")

router = APIRouter()


@router.post("/", response_model=User, status_code=201)
def create_user(
    user_in: UserCreate, db: Session = Depends(get_db)
) -> Any:  # pragma: no cover - (Covered by test_user_creation_and_login)
    """
    Create new user.
    """
    db_user = db.query(UserModel).filter(UserModel.email == user_in.email).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    db_user = db.query(UserModel).filter(UserModel.username == user_in.username).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )

    hashed_password = get_password_hash(user_in.password)
    db_user = UserModel(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password,
        # Removed automatic API key generation on user creation
        # api_key=generate_forge_api_key(), # Users will create keys via /api-keys endpoint
        is_active=True,  # Default to active, admin can deactivate
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Create default TensorBlock provider for the new user
    try:
        create_default_tensorblock_provider_for_user(db_user.id, db)
    except Exception as e:
        # Log error but don't fail user creation
        logger.warning(
            f"Failed to create default TensorBlock provider for user {db_user.id}: {e}"
        )

    return db_user


@router.get("/me", response_model=MaskedUser)
def read_user_me(
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    # Construct the response using MaskedUser to ensure API keys are masked
    user_data = current_user.__dict__.copy()
    if hasattr(current_user, "api_keys") and current_user.api_keys:
        user_data["forge_api_keys"] = [
            MaskedUser.mask_api_key(api_key.key) for api_key in current_user.api_keys
        ]
    else:
        user_data["forge_api_keys"] = []

    return MaskedUser(**user_data)


@router.get("/me/clerk", response_model=MaskedUser)
def read_user_me_clerk(
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    """
    Get current user from Clerk.
    """
    user_data = current_user.__dict__.copy()
    if hasattr(current_user, "api_keys") and current_user.api_keys:
        user_data["forge_api_keys"] = [
            MaskedUser.mask_api_key(api_key.key) for api_key in current_user.api_keys
        ]
    else:
        user_data["forge_api_keys"] = []

    return MaskedUser(**user_data)


@router.put("/me", response_model=User)
def update_user_me(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    """
    Update current user.
    """
    if user_in.username:
        current_user.username = user_in.username
    if user_in.email:
        current_user.email = user_in.email
    if user_in.password:
        current_user.hashed_password = get_password_hash(user_in.password)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    invalidate_user_cache(
        current_user.id
    )  # Assuming user_id is the cache key for user object
    # If API key was part of user model directly and changed, invalidate its cache too.
    # However, API keys are now separate, so user update doesn't directly affect API key string caches
    # unless an API key string was derived directly from user fields that changed.
    return current_user


@router.put("/me/clerk", response_model=User)
def update_user_me_clerk(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    """
    Update current user from Clerk.
    """
    return update_user_me(user_in, db, current_user)


# The regenerate_api_key and regenerate_api_key_clerk endpoints have been removed.
# Users should now use the POST /api-keys/ endpoint to create new Forge API keys
# and manage them via GET /api-keys/, PUT /api-keys/{key_id}, and DELETE /api-keys/{key_id}.

# @router.post("/regenerate-api-key", response_model=dict) ... (Removed)
# @router.post("/regenerate-api-key/clerk", response_model=User) ... (Removed)
