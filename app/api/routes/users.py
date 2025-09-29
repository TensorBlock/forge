from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_current_active_user_from_clerk
from app.api.schemas.user import User, UserCreate, UserUpdate, MaskedUser
from app.core.database import get_async_db
from app.core.security import get_password_hash
from app.core.logger import get_logger
from app.models.user import User as UserModel
from app.services.provider_service import create_default_tensorblock_provider_for_user

logger = get_logger(name="users")

router = APIRouter()


@router.post("/", response_model=User)
async def create_user(
    user_in: UserCreate, db: AsyncSession = Depends(get_async_db)
) -> Any:
    """
    Create a new user.
    """
    # Check if email already exists
    result = await db.execute(
        select(UserModel).filter(UserModel.email == user_in.email)
    )
    db_user = result.scalar_one_or_none()
    if db_user:
        raise HTTPException(
            status_code=400, detail="Email already registered"
        )
    
    # Check if username already exists
    result = await db.execute(
        select(UserModel).filter(UserModel.username == user_in.username)
    )
    db_user = result.scalar_one_or_none()
    if db_user:
        raise HTTPException(
            status_code=400, detail="Username already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_in.password)
    db_user = UserModel(
        email=user_in.email,
        username=user_in.username,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Create default TensorBlock provider for the new user
    try:
        await create_default_tensorblock_provider_for_user(db_user.id, db)
    except Exception as e:
        # Log error but don't fail user creation
        logger.error({
            "message": f"Error creating default TensorBlock provider for user {db_user.id}",
            "extra": {
                "error": str(e),
            }
        })

    return db_user


@router.get("/me", response_model=MaskedUser)
async def read_user_me(
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

    if current_user.admin_users:
        user_data["is_admin"] = True

    return MaskedUser(**user_data)


@router.get("/me/clerk", response_model=MaskedUser)
async def read_user_me_clerk(
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

    if current_user.admin_users:
        user_data["is_admin"] = True

    return MaskedUser(**user_data)


@router.put("/me", response_model=User)
async def update_user_me(
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_async_db),
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
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.put("/me/clerk", response_model=User)
async def update_user_me_clerk(
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_active_user_from_clerk),
) -> Any:
    """
    Update current user from Clerk.
    """
    return await update_user_me(user_in, db, current_user)


# The regenerate_api_key and regenerate_api_key_clerk endpoints have been removed.
# Users should now use the POST /api-keys/ endpoint to create new Forge API keys
# and manage them via GET /api-keys/, PUT /api-keys/{key_id}, and DELETE /api-keys/{key_id}.

# @router.post("/regenerate-api-key", response_model=dict) ... (Removed)
# @router.post("/regenerate-api-key/clerk", response_model=User) ... (Removed)
