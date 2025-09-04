import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
import stripe
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from svix import Webhook, WebhookVerificationError

from app.core.database import get_async_db
from app.core.logger import get_logger
from app.models.user import User
from app.models.stripe import StripePayment
from app.services.provider_service import create_default_tensorblock_provider_for_user
from app.services.wallet_service import WalletService

logger = get_logger(name="webhooks")

router = APIRouter()

# Webhook signing secrets for verifying webhook authenticity
CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


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


@router.post("/stripe")
async def stripe_webhook_handler(request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Handle Stripe webhooks for payment events.
    
    Key events to handle:
    - checkout.session.async_payment_succeeded / checkout.session.completed: Credit wallet balance
    - checkout.session.async_payment_failed: Log failed payment
    - checkout.session.expired: Log expired payment
    """
    # Get the request body and signature
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing Stripe signature header"
        )
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        # For now, parse as JSON (would use verified event in production)
        event_type = event.get("type")
        
        logger.info(f"Received Stripe webhook: {event_type}")

        # Handle different event types
        if event_type in ["checkout.session.async_payment_succeeded", "checkout.session.completed"]:
            await handle_payment_succeeded(event, db)
        elif event_type == "checkout.session.async_payment_failed":
            await handle_payment_failed(event, db)
        elif event_type == "checkout.session.expired":
            await handle_payment_expired(event, db)
        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")

        return {"status": "success", "message": f"Event {event_type} processed"}
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}",
        )


async def handle_payment_succeeded(event: dict, db: AsyncSession):
    """Handle successful payment - credit wallet balance"""
    try:
        session = event.get("data", {}).get("object", {})
        if not session:
            logger.warning("Checkout payment intent not found in event")
            return

        session_id = session['id']
        amount = session['amount_total']
        currency = session['currency'].upper()
        status = session['status']
        payment_status = session['payment_status']

        if status == "complete" and payment_status == "paid":
            status = "completed"
        else:
            status = payment_status or "failed"

        # update the corresponding StripePayment db record and return the user id
        result = await db.execute(
            update(StripePayment).where(StripePayment.id == session_id).values(
                status = status,
                amount = amount,
                currency = currency,
                raw_data = session,
            ).returning(StripePayment.user_id)
        )
        user_id = result.scalar_one_or_none()
        if not user_id:
            logger.warning(f"Stripe payment not found for id {id}")
            return
        
        if status != "completed":
            logger.warning(f"Received payment success event for non-completed session: {session_id}")
            return

        # Convert cents to dollars for USD
        if currency == "USD":
            amount_decimal = amount / 100.0
        else:
            amount_decimal = amount  # Handle other currencies as needed
        
        logger.info(f"Payment succeeded: {amount_decimal} {currency} for customer {user_id}")
        
        await WalletService.adjust(
            db, 
            user_id, 
            amount_decimal, 
            f"deposit:stripe:{session_id}", 
            currency
        )
        
    except Exception as e:
        logger.error(f"Failed to process payment success: {e}", exc_info=True)
        raise

async def handle_payment_failed(event: dict, db: AsyncSession):
    """Handle failed payment"""
    try:
        session = event.get("data", {}).get("object", {})
        if not session:
            logger.warning("Checkout session not found in event")
            return
        
        session_id = session['id']
        status = session['status']
        payment_status = session['payment_status']
        
        # update the corresponding StripePayment db record and return the user id
        result = await db.execute(
            update(StripePayment).where(StripePayment.id == session_id).values(
                status = payment_status or status,
                raw_data = session,
            ).returning(StripePayment.user_id)
        )
        user_id = result.scalar_one_or_none()
        if not user_id:
            logger.warning(f"Stripe payment not found for id {session_id}")
            return
        
        logger.warning(f"Payment failed: {session_id} for customer {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to process payment failed: {e}", exc_info=True)
        raise
    

async def handle_payment_expired(event: dict, db: AsyncSession):
    """Handle expired payment"""
    try:
        session = event.get("data", {}).get("object", {})
        if not session:
            logger.warning("Checkout session not found in event")
            return
        
        session_id = session['id']
        status = session['status']
        
        # update the corresponding StripePayment db record and return the user id
        result = await db.execute(
            update(StripePayment).where(StripePayment.id == session_id).values(
                status = status,
                raw_data = session,
            ).returning(StripePayment.user_id)
        )
        user_id = result.scalar_one_or_none()
        if not user_id:
            logger.warning(f"Stripe payment not found for id {session_id}")
            return
        
        logger.warning(f"Payment expired: {session_id} for customer {user_id}")

    except Exception as e:
        logger.error(f"Failed to process payment expired: {e}", exc_info=True)
        raise