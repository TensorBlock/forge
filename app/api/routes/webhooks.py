import json
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from svix.webhooks import Webhook, WebhookVerificationError

from app.core.database import get_db
from app.core.logger import get_logger
from app.core.security import generate_forge_api_key
from app.models.user import User
from app.services.provider_service import create_default_tensorblock_provider_for_user

logger = get_logger(name="webhooks")

router = APIRouter()

# Clerk webhook signing secret for verifying webhook authenticity
CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET", "")


@router.post("/clerk")
async def clerk_webhook_handler(request: Request, db: Session = Depends(get_db)):
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
            # Check if user already exists
            user = db.query(User).filter(User.clerk_user_id == clerk_user_id).first()
            if user:
                return {"status": "success", "message": "User already exists"}

            # Check if user exists with this email
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                # Link existing user to Clerk ID
                try:
                    existing_user.clerk_user_id = clerk_user_id
                    db.commit()
                    return {"status": "success", "message": "Linked to existing user"}
                except IntegrityError:
                    # Another request might have already linked this user or created a new one
                    db.rollback()
                    # Retry the query to get the user
                    user = (
                        db.query(User)
                        .filter(User.clerk_user_id == clerk_user_id)
                        .first()
                    )
                    if user:
                        return {"status": "success", "message": "User already exists"}
                    # If still no user, continue with creation attempt

            # Create new user
            forge_api_key = generate_forge_api_key()

            try:
                user = User(
                    email=email,
                    username=username,
                    clerk_user_id=clerk_user_id,
                    is_active=True,
                    forge_api_key=forge_api_key,
                )
                db.add(user)
                db.commit()

                # Create default TensorBlock provider for the new user
                try:
                    create_default_tensorblock_provider_for_user(user.id, db)
                except Exception as e:
                    # Log error but don't fail user creation
                    logger.warning(
                        f"Failed to create default TensorBlock provider for user {user.id}: {e}"
                    )

                return {"status": "success", "message": "User created"}
            except IntegrityError as e:
                # Handle race condition: another request might have created the user
                db.rollback()
                if "users_clerk_user_id_key" in str(e) or "clerk_user_id" in str(e):
                    # Retry the query to get the user that was created by another request
                    user = (
                        db.query(User)
                        .filter(User.clerk_user_id == clerk_user_id)
                        .first()
                    )
                    if user:
                        return {"status": "success", "message": "User already exists"}
                    else:
                        # This shouldn't happen, but handle it gracefully
                        return {
                            "status": "error",
                            "message": "Failed to create user due to database constraint",
                        }
                else:
                    # Re-raise other integrity errors
                    raise

        elif event_type == "user.updated":
            # Update user if they exist
            user = db.query(User).filter(User.clerk_user_id == clerk_user_id).first()
            if not user:
                return {"status": "error", "message": "User not found"}

            # Update fields
            if email and user.email != email:
                user.email = email
            if username and user.username != username:
                user.username = username

            db.commit()
            return {"status": "success", "message": "User updated"}

        elif event_type == "user.deleted":
            # Deactivate user rather than delete
            user = db.query(User).filter(User.clerk_user_id == clerk_user_id).first()
            if user:
                user.is_active = False
                db.commit()
                return {"status": "success", "message": "User deactivated"}

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
