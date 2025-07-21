import asyncio
import contextlib
import json

# Add environment variables for Clerk
import os
import time
from datetime import datetime

import aiohttp
import requests
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.schemas.user import TokenData
from app.core.async_cache import (
    cache_user_async,
    get_cached_user_async,
    invalidate_user_cache_async,
    forge_scope_cache_async,
    get_forge_scope_cache_async,
)
from app.core.database import get_db, get_async_db
from app.core.logger import get_logger
from app.core.security import (
    ALGORITHM,
    SECRET_KEY,
)
from app.models.forge_api_key import ForgeApiKey
from app.models.user import User
from app.services.provider_service import create_default_tensorblock_provider_for_user

logger = get_logger(name="dependencies")

CLERK_API_KEY = os.getenv("CLERK_API_KEY")
CLERK_API_URL = os.getenv("CLERK_API_URL", "https://api.clerk.dev/v1")

# API key validation constants
MIN_API_KEY_LENGTH = 5

# --- JWKS Configuration ---
CLERK_JWKS_URL = os.getenv(
    "CLERK_JWKS_URL",
    "https://pleased-anemone-64.clerk.accounts.dev/.well-known/jwks.json",
)
_jwks_cache = {"keys": None, "expiry": 0.0}
JWKS_CACHE_TTL_SECONDS = 3600
_jwks_lock = asyncio.Lock()
# --- End JWKS Configuration ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
clerk_token_header = APIKeyHeader(name="Authorization", auto_error=False)


async def fetch_and_cache_jwks() -> list | None:
    """Fetches JWKS from Clerk, caches them, and returns the keys."""
    current_time = time.time()
    if _jwks_cache["keys"] and _jwks_cache["expiry"] > current_time:
        return _jwks_cache["keys"]

    async with _jwks_lock:
        if _jwks_cache["keys"] and _jwks_cache["expiry"] > current_time:
            return _jwks_cache["keys"]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(CLERK_JWKS_URL) as response:
                    response.raise_for_status()
                    jwks_json = await response.json()
                    _jwks_cache["keys"] = jwks_json.get("keys", [])
                    _jwks_cache["expiry"] = current_time + JWKS_CACHE_TTL_SECONDS
                    if os.getenv("DEBUG") == "true":
                        logger.debug(
                            f"Successfully fetched and cached JWKS. Keys: {len(_jwks_cache['keys'])}"
                        )
                    return _jwks_cache["keys"]
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch JWKS from {CLERK_JWKS_URL}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JWKS JSON from {CLERK_JWKS_URL}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching JWKS: {e}")

        if _jwks_cache["keys"] and _jwks_cache["expiry"] <= current_time:
            _jwks_cache["keys"] = None
        return _jwks_cache["keys"]


async def get_current_user(
    db: AsyncSession = Depends(get_async_db), token: str = Depends(oauth2_scheme)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials for local user",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError as err:
        raise credentials_exception from err
    
    result = await db.execute(select(User).filter(User.username == token_data.username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_api_key_from_headers(request: Request) -> str:
    """Get API key from various possible header formats"""
    # Try different header names
    api_key = request.headers.get("X-API-KEY")
    if api_key:
        return api_key

    api_key = request.headers.get("Authorization")
    if api_key and api_key.startswith("Bearer "):
        return api_key[7:]  # Remove "Bearer " prefix

    api_key = request.headers.get("api-key")
    if api_key:
        return api_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API key not found in headers",
    )


async def get_user_by_api_key(
    request: Request = None,
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Get user by API key from headers, with caching"""
    api_key_from_header = await get_api_key_from_headers(request)

    # Lightweight API key format verification
    if (
        not api_key_from_header.startswith("forge-")
        or len(api_key_from_header) < MIN_API_KEY_LENGTH
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    # The part of the key after "forge-" is used for caching.
    api_key = api_key_from_header[6:]

    # Store the API key on the request state for downstream handlers (e.g., to avoid
    # calling get_api_key_from_headers again).
    if request is not None:
        with contextlib.suppress(AttributeError):
            request.state.forge_api_key = api_key

    # Try to get user from cache first
    cached_user = await get_cached_user_async(api_key)
    if cached_user is not None:
        if not cached_user.is_active:
            await invalidate_user_cache_async(api_key)
            raise HTTPException(status_code=400, detail="Inactive user")

        # Return a transient User object from cached data, not a managed one.
        # This avoids the db.merge() call and its expensive SELECT query.
        # Downstream code can access attributes, but not lazy-load relationships.
        return User(**cached_user.model_dump())

    # Try scope cache first – this doesn't remove the need to verify the key, but it
    # avoids an extra query later in /models.
    cached_scope = await get_forge_scope_cache_async(api_key)

    result = await db.execute(
        select(ForgeApiKey)
        .options(selectinload(ForgeApiKey.allowed_provider_keys))
        .filter(ForgeApiKey.key == api_key_from_header, ForgeApiKey.is_active)
    )
    api_key_record = result.scalar_one_or_none()

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Get the user associated with this API key and EAGER LOAD all provider keys
    result = await db.execute(
        select(User)
        .options(selectinload(User.provider_keys))
        .filter(User.id == api_key_record.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for API key",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Determine the allowed provider scope for this key (None means unrestricted)
    if cached_scope is None:
        allowed_provider_names = [
            pk.provider_name for pk in api_key_record.allowed_provider_keys
        ]
        # Cache it (short TTL – scope changes are rare)
        await forge_scope_cache_async(api_key, allowed_provider_names, ttl=300)
    else:
        allowed_provider_names = cached_scope

    # Store on request.state for downstream use
    if request is not None:
        with contextlib.suppress(AttributeError):
            request.state.allowed_provider_names = allowed_provider_names

    # Update last used timestamp for the API key
    api_key_record.last_used_at = datetime.utcnow()
    await db.commit()

    # Cache the user data for future requests
    await cache_user_async(api_key, user)

    return user


async def validate_clerk_jwt(token: str = Depends(clerk_token_header)):
    """
    Validate a Clerk JWT token using JWKS from Clerk.
    """
    if not token or not token.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = token.replace("Bearer ", "")

    try:
        # For development/testing, allow decoding without verification
        if os.getenv("TESTING") == "true":
            payload = jwt.decode(
                token, options={"verify_signature": False, "verify_exp": False}
            )
            logger.debug(f"TEST MODE: Token accepted for user {payload.get('sub')}")
            return payload

        # Get the key ID (kid) from the JWT header
        unverified_header = jwt.get_unverified_header(token)
        if not unverified_header or "kid" not in unverified_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'kid' in header",
            )
        kid = unverified_header["kid"]

        # Fetch (and cache) JWKS keys
        jwks_keys = await fetch_and_cache_jwks()
        if not jwks_keys:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not fetch or cache Clerk public keys (JWKS).",
            )

        matching_key = None
        for key_data in jwks_keys:
            if key_data.get("kid") == kid:
                matching_key = key_data
                break

        if not matching_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Public key with kid='{kid}' not found in JWKS.",
            )

        # Get the algorithm from the header (or from the JWK itself)
        alg = unverified_header.get("alg")
        if not alg:
            alg = matching_key.get("alg")
        if not alg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Algorithm not found in token or JWK.",
            )

        # Verify the token with the appropriate key and algorithm
        payload = jwt.decode(
            token,
            matching_key,
            algorithms=[alg],
            options={
                "verify_signature": True,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
        return payload

    except JWTError as e:
        if os.getenv("DEBUG") == "true":
            import traceback

            logger.debug(f"JWT validation error: {str(e)}")
            logger.debug(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        if os.getenv("DEBUG") == "true":
            import traceback

            logger.debug(f"Unexpected error during JWT validation: {str(e)}")
            logger.debug(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during token validation: {str(e)}",
        )


async def get_current_user_from_clerk(
    db: AsyncSession = Depends(get_async_db), token_payload: dict = Depends(validate_clerk_jwt)
):
    """Get the current user from Clerk token, creating if needed"""
    from urllib.parse import quote

    clerk_user_id = token_payload.get("sub")

    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user information in token: missing user ID",
        )

    # Find user by clerk_user_id
    result = await db.execute(select(User).filter(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    # User doesn't exist yet, create one
    if not user:
        # Fetch user data from Clerk API
        clerk_api_key = os.getenv("CLERK_API_KEY")
        if not clerk_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk API key not configured",
            )

        # Call Clerk API to get user info
        clerk_api_url = os.getenv("CLERK_API_URL", "https://api.clerk.dev/v1")
        url = f"{clerk_api_url}/users/{quote(clerk_user_id)}"

        try:
            response = requests.get(
                url, headers={"Authorization": f"Bearer {clerk_api_key}"}
            )

            if not response.ok:
                raise ValueError(
                    f"Clerk API error: {response.status_code} - {response.text}"
                )

            user_data = response.json()

            # Extract email address
            email = None
            if user_data.get("primary_email_address_id") and user_data.get(
                "email_addresses"
            ):
                for email_obj in user_data.get("email_addresses", []):
                    if email_obj.get("id") == user_data.get("primary_email_address_id"):
                        email = email_obj.get("email_address")
                        break

            # Fallback if no email found
            if not email:
                email = f"{clerk_user_id}@placeholder.com"

            # Use email as username directly
            username = email

            # Check if username exists and make unique if needed
            result = await db.execute(select(User).filter(User.username == username))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                import random

                username = f"{username.split('@')[0]}{random.randint(100, 999)}@{username.split('@')[1]}"

        except Exception as e:
            if os.getenv("DEBUG") == "true":
                logger.debug(f"Error fetching Clerk user data: {e}")
            # Fallback to placeholder values
            email = f"{clerk_user_id}@placeholder.com"
            username = clerk_user_id

        # Check if user exists with this email
        result = await db.execute(select(User).filter(User.email == email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            # Link existing user to Clerk ID
            try:
                existing_user.clerk_user_id = clerk_user_id
                await db.commit()
                return existing_user
            except IntegrityError:
                # Another request might have already linked this user or created a new one
                await db.rollback()
                # Retry the query to get the user
                result = await db.execute(
                    select(User).filter(User.clerk_user_id == clerk_user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    return user
                # If still no user, continue with creation attempt

        # Create new user
        from app.core.security import get_password_hash

        try:
            user = User(
                email=email,
                username=username,
                clerk_user_id=clerk_user_id,
                is_active=True,
                hashed_password="",  # Clerk handles authentication
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            # Create default TensorBlock provider for the new user
            try:
                await create_default_tensorblock_provider_for_user(user.id, db)
            except Exception as e:
                # Log error but don't fail user creation
                logger.warning(
                    f"Failed to create default TensorBlock provider for user {user.id}: {e}"
                )

            return user
        except IntegrityError as e:
            # Handle race condition: another request might have created the user
            await db.rollback()
            if "users_clerk_user_id_key" in str(e) or "clerk_user_id" in str(e):
                # Retry the query to get the user that was created by another request
                result = await db.execute(
                    select(User).filter(User.clerk_user_id == clerk_user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    return user
                else:
                    # This shouldn't happen, but handle it gracefully
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create or retrieve user due to database constraint",
                    )
            else:
                # Re-raise other integrity errors
                raise

    return user


async def get_current_active_user_from_clerk(
    current_user: User = Depends(get_current_user_from_clerk),
):
    """Ensure the user from Clerk is active"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
