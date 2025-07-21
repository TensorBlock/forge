import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from svix import Webhook, WebhookVerificationError

from app.core.database import get_async_db
from app.core.logger import get_logger
from app.core.security import generate_forge_api_key
from app.models.user import User
from app.services.provider_service import create_default_tensorblock_provider_for_user

logger = get_logger(name="webhooks")

router = APIRouter()

# Clerk webhook signing secret for verifying webhook authenticity
CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET", "")


@router.post("/clerk")
async def clerk_webhook_handler(request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Handle Clerk webhooks for user events.

    Key events to handle:
    - user.created: Create a new user in our database
    - user.updated: Update user details
    - user.deleted: Optionally deactivate the user
    """
    # Get the request body
    payload = await request.body()

    # Get headers for Svix verification
    svix_id = request.headers.get("svix-id")
    svix_timestamp = request.headers.get("svix-timestamp")
    svix_signature = request.headers.get("svix-signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Svix headers"
        )

    # Prepare headers for verification
    svix_headers = {
        "svix-id": svix_id,
        "svix-timestamp": svix_timestamp,
        "svix-signature": svix_signature,
    }

    # Verify webhook signature with Svix
    try:
        if not CLERK_WEBHOOK_SECRET:
            # For development only - should be removed in production
            logger.warning("CLERK_WEBHOOK_SECRET is not set")
        else:
            wh = Webhook(CLERK_WEBHOOK_SECRET)
            # This will throw an error if verification fails
            wh.verify(payload.decode(), svix_headers)
    except WebhookVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid webhook signature: {str(e)}",
        )

    # Parse the event
    try:
        event_data = json.loads(payload)
        event_type = event_data.get("type")

        # Extract user data
        user_data = event_data.get("data", {})
        clerk_user_id = user_data.get("id")

        # Extract email from email_addresses array
        email_addresses = user_data.get("email_addresses", [])
        primary_email_id = user_data.get("primary_email_address_id")

        email = None
        # Find primary email
        for email_obj in email_addresses:
            if email_obj.get("id") == primary_email_id:
                email = email_obj.get("email_address")
                break

        # If no primary email, use the first one
        if not email and email_addresses:
            email = email_addresses[0].get("email_address", "")

        # Get username or fallback to email prefix
        username = user_data.get("username")
        if not username and email:
            username = email.split("@")[0]

        if not clerk_user_id or not email:
            return {"status": "error", "message": "Missing required user data"}

        # Handle different event types
        if event_type == "user.created":
            await handle_user_created(event_data, db)

        elif event_type == "user.updated":
            await handle_user_updated(event_data, db)

        elif event_type == "user.deleted":
            await handle_user_deleted(event_data, db)

        return {"status": "success", "message": f"Event {event_type} processed"}

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}",
        )


async def handle_user_created(event_data: dict, db: AsyncSession):
    """Handle user.created event from Clerk"""
    try:
        clerk_user_id = event_data.get("id")
        email = event_data.get("email_addresses", [{}])[0].get("email_address", "")
        username = (
            event_data.get("username")
            or event_data.get("first_name", "")
            or email.split("@")[0]
        )

        logger.info(f"Creating user from Clerk webhook: {username} ({email})")

        # Check if user already exists by clerk_user_id
        result = await db.execute(
            select(User).filter(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            logger.info(f"User {username} already exists with Clerk ID")
            return

        # Check if user exists with this email
        result = await db.execute(
            select(User).filter(User.email == email)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            # Link existing user to Clerk ID
            existing_user.clerk_user_id = clerk_user_id
            await db.commit()
            logger.info(f"Linked existing user {existing_user.username} to Clerk ID")
            return

        # Create new user
        user = User(
            username=username,
            email=email,
            clerk_user_id=clerk_user_id,
            is_active=True,
            hashed_password="",  # Clerk handles authentication
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Create default provider for the user
        create_default_tensorblock_provider_for_user(user.id, db)

        logger.info(f"Successfully created user {username} with ID {user.id}")

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create user from webhook: {e}", exc_info=True)
        raise


async def handle_user_updated(event_data: dict, db: AsyncSession):
    """Handle user.updated event from Clerk"""
    try:
        clerk_user_id = event_data.get("id")
        email = event_data.get("email_addresses", [{}])[0].get("email_address", "")
        username = (
            event_data.get("username")
            or event_data.get("first_name", "")
            or email.split("@")[0]
        )

        logger.info(f"Updating user from Clerk webhook: {username} ({email})")

        result = await db.execute(
            select(User).filter(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"User with Clerk ID {clerk_user_id} not found for update")
            return

        # Update user information
        user.username = username
        user.email = email
        await db.commit()

        logger.info(f"Successfully updated user {username}")

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update user from webhook: {e}", exc_info=True)
        raise


async def handle_user_deleted(event_data: dict, db: AsyncSession):
    """Handle user.deleted event from Clerk"""
    try:
        clerk_user_id = event_data.get("id")

        logger.info(f"Deleting user from Clerk webhook: {clerk_user_id}")

        result = await db.execute(
            select(User).filter(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"User with Clerk ID {clerk_user_id} not found for deletion")
            return

        # Deactivate user instead of deleting to preserve data integrity
        user.is_active = False
        await db.commit()

        logger.info(f"Successfully deactivated user {user.username}")

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete user from webhook: {e}", exc_info=True)
        raise
