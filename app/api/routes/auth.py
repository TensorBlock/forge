from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.users import create_user as create_user_endpoint_logic
from app.api.schemas.user import Token, User, UserCreate
from app.core.database import get_async_db
from app.core.logger import get_logger
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    verify_password,
)
from app.models.user import User as UserModel

logger = get_logger(name="auth")

router = APIRouter()


@router.post("/register", response_model=User)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """
    Register new user. This will create the user but will not automatically create a Forge API key.
    Users should use the /api-keys/ endpoint to create their keys after registration.
    """
    # Call the user creation logic from users.py
    # This handles checks for existing email/username and password hashing.
    try:
        db_user = await create_user_endpoint_logic(user_in=user_in, db=db)
    except HTTPException as e:  # Propagate HTTPExceptions (like 400 for existing user)
        raise e
    except Exception as e:  # Catch any other unexpected errors during user creation
        # Log this error e
        logger.error(
            f"Unexpected error during create_user_endpoint_logic call: {e}"
        )  # Added more logging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during user registration.",
        )

    # Prepare the response.
    # create_user_endpoint_logic returns a UserModel instance.
    # The User Pydantic model has from_attributes = True.
    try:
        # For Pydantic v2+ (which is likely if using FastAPI > 0.100.0)
        pydantic_user = User.model_validate(db_user)
        # If using Pydantic v1, you would use:
        # pydantic_user = User.from_orm(db_user)
    except Exception as e_pydantic:
        # Log this validation error to understand what went wrong if it fails
        logger.error(
            f"Error during Pydantic model_validate in /auth/register: {e_pydantic}"
        )
        logger.error(
            f"SQLAlchemy User object was: {db_user.__dict__ if db_user else 'None'}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing user data after creation.",
        )

    pydantic_user.forge_api_keys = []  # Explicitly set to empty list as no key is auto-generated

    return pydantic_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    db: AsyncSession = Depends(get_async_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Get an access token for future API requests.
    """
    result = await db.execute(
        select(UserModel).filter(UserModel.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
