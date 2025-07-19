import os
import time
from typing import Any
from urllib.parse import quote

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_active_user,
    get_current_active_user_from_clerk,
)
from app.api.schemas.user import User
from app.core.database import get_async_db
from app.models.user import User as UserModel

router = APIRouter()


async def get_user_from_any_auth(
    db: AsyncSession = Depends(get_async_db),
    jwt_user: UserModel | None = Depends(get_current_active_user),
    clerk_user: UserModel | None = Depends(get_current_active_user_from_clerk),
) -> UserModel:
    """
    Try to authenticate user with both JWT and Clerk methods.
    Will use the first successful authentication.
    """
    # If JWT auth succeeded, use that user
    if jwt_user:
        return jwt_user

    # If Clerk auth succeeded, use that user
    if clerk_user:
        return clerk_user

    # If neither auth method worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication failed",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/me", response_model=User)
async def get_unified_current_user(
    current_user: UserModel = Depends(get_user_from_any_auth),
) -> Any:
    """
    Get current user using any authentication method (JWT or Clerk).
    Frontend can use this single endpoint regardless of auth method.
    """
    return current_user


@router.get("/debug/token")
async def debug_token(request: Request):
    """
    Debug endpoint to analyze a token without actually authenticating.
    This is helpful for diagnosing token issues.
    """
    token_header = request.headers.get("Authorization", "")

    if not token_header or not token_header.startswith("Bearer "):
        return {
            "valid": False,
            "error": "No token provided or invalid format",
            "help": "Use Authorization: Bearer <your_token>",
        }

    token = token_header.replace("Bearer ", "")

    try:
        # First, try to decode without verification to see the claims
        unverified_payload = jwt.decode(token, options={"verify_signature": False})

        result = {
            "token_format": "valid",
            "algorithm": unverified_payload.get("alg", "unknown"),
            "unverified_claims": unverified_payload,
            "subject": unverified_payload.get("sub"),
            "issuer": unverified_payload.get("iss"),
            "audience": unverified_payload.get("azp") or unverified_payload.get("aud"),
            "expiration": unverified_payload.get("exp"),
        }

        # Get token header
        header_base64 = token.split(".")[0]
        import base64

        header_str = base64.urlsafe_b64decode(
            header_base64 + "=" * (4 - len(header_base64) % 4)
        )
        header = jwt.json.loads(header_str)
        result["header"] = header
        result["token_type"] = header.get("typ")
        result["actual_algorithm"] = header.get("alg")

        # Check for common issues
        issues = []

        # 1. Check if we're expecting RS256 but got ES256 or vice versa
        clerk_pub_key = os.getenv("CLERK_JWT_PUBLIC_KEY")
        if not clerk_pub_key:
            issues.append("CLERK_JWT_PUBLIC_KEY environment variable is not set")
        elif "-----BEGIN PUBLIC KEY-----" not in clerk_pub_key:
            issues.append(
                "CLERK_JWT_PUBLIC_KEY does not look like a valid PEM format public key"
            )

        if header.get("alg") == "RS256" and "ES256" in issues:
            issues.append("Token uses RS256 algorithm but we're expecting ES256")

        # 2. Check for audience issues
        expected_audience = os.getenv("APP_DOMAIN") or "your-app-domain"
        actual_audience = unverified_payload.get("azp") or unverified_payload.get("aud")
        if actual_audience and expected_audience != actual_audience:
            issues.append(
                f"Token audience mismatch: expected '{expected_audience}', got '{actual_audience}'"
            )

        # Add issues to result
        if issues:
            result["issues"] = issues
            result["help"] = "Fix the issues above to validate the token correctly"
        else:
            result["issues"] = []

        return result
    except Exception as e:
        return {
            "valid": False,
            "error": f"Invalid token format: {str(e)}",
            "help": "Make sure you're using a valid JWT token",
        }


@router.get("/debug/token-expiry")
async def debug_token_expiry(request: Request):
    """Debug endpoint to check token expiration status"""
    token_header = request.headers.get("Authorization", "")

    if not token_header or not token_header.startswith("Bearer "):
        return {
            "error": "Invalid Authorization header",
            "help": "Use 'Authorization: Bearer <your_token>'",
        }

    token = token_header.replace("Bearer ", "")

    try:
        # Decode without verification - use empty string as key when verify_signature=False
        payload = jwt.decode(
            token, key="", options={"verify_signature": False, "verify_exp": False}
        )

        # Check expiration
        exp = payload.get("exp", 0)
        current_time = int(time.time())

        is_expired = exp < current_time

        if is_expired:
            minutes_ago = (current_time - exp) // 60
            expiry_message = f"Token expired {minutes_ago} minutes ago"
        else:
            minutes_left = (exp - current_time) // 60
            expiry_message = f"Token valid for {minutes_left} more minutes"

        # Extract useful info
        sub = payload.get("sub", "unknown")

        return {
            "is_expired": is_expired,
            "expiry_status": expiry_message,
            "user_id": sub,
            "token_info": {
                "issued_at": payload.get("iat", 0),
                "expires_at": exp,
                "current_time": current_time,
            },
        }
    except Exception as e:
        return {
            "error": f"Failed to decode token: {str(e)}",
            "help": "Make sure you're providing a valid JWT token",
        }


@router.get("/debug/jwt")
async def debug_jwt(request: Request):
    """Debug endpoint to inspect JWT structure"""
    token_header = request.headers.get("Authorization", "")

    if not token_header or not token_header.startswith("Bearer "):
        return {
            "error": "Invalid Authorization header",
            "help": "Use 'Authorization: Bearer <your_token>'",
        }

    token = token_header.replace("Bearer ", "")

    try:
        # Decode without verification - use empty string as key when verify_signature=False
        payload = jwt.decode(
            token, key="", options={"verify_signature": False, "verify_exp": False}
        )

        # Return the full token payload for inspection
        return {
            "payload": payload,
            "user_info": {
                "sub": payload.get("sub"),
                "email_claims": {
                    "email": payload.get("email"),
                    "email_in_metadata": payload.get("metadata", {}).get("email")
                    if payload.get("metadata")
                    else None,
                },
                "name_claims": {
                    "name": payload.get("name"),
                    "username": payload.get("username"),
                    "given_name": payload.get("given_name"),
                    "family_name": payload.get("family_name"),
                },
            },
        }
    except Exception as e:
        return {
            "error": f"Failed to decode token: {str(e)}",
            "help": "Make sure you're providing a valid JWT token",
        }


@router.get("/debug/clerk-user")
async def debug_clerk_user(request: Request):
    """Debug endpoint to fetch user info from Clerk API"""
    token_header = request.headers.get("Authorization", "")

    if not token_header or not token_header.startswith("Bearer "):
        return {
            "error": "Invalid Authorization header",
            "help": "Use 'Authorization: Bearer <your_token>'",
        }

    token = token_header.replace("Bearer ", "")

    try:
        # Decode to get user ID
        payload = jwt.decode(
            token, key="", options={"verify_signature": False, "verify_exp": False}
        )
        clerk_user_id = payload.get("sub")

        if not clerk_user_id:
            return {"error": "No user ID found in token"}

        # Get Clerk API key from environment
        clerk_api_key = os.getenv("CLERK_API_KEY")
        if not clerk_api_key:
            return {"error": "Clerk API key not configured"}

        # Call Clerk API to get user info
        clerk_api_url = os.getenv("CLERK_API_URL", "https://api.clerk.dev/v1")
        url = f"{clerk_api_url}/users/{quote(clerk_user_id)}"

        response = requests.get(
            url, headers={"Authorization": f"Bearer {clerk_api_key}"}
        )

        if not response.ok:
            return {
                "error": f"Failed to fetch user data: {response.status_code}",
                "details": response.text,
            }

        user_data = response.json()

        # Extract the important fields
        user_info = {
            "id": user_data.get("id"),
            "email_addresses": user_data.get("email_addresses", []),
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "created_at": user_data.get("created_at"),
            "updated_at": user_data.get("updated_at"),
            "primary_email_address": None,
        }

        # Find primary email
        for email in user_data.get("email_addresses", []):
            if email.get("id") == user_data.get("primary_email_address_id"):
                user_info["primary_email_address"] = email.get("email_address")
                break

        return {
            "user_info": user_info,
            "token_sub": clerk_user_id,
            "raw_response": user_data,  # Include full response for debugging
        }
    except Exception as e:
        return {"error": f"Failed to fetch user data: {str(e)}"}
