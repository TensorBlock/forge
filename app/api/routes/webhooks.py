import json
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
import stripe
from sqlalchemy import update, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from svix import Webhook, WebhookVerificationError
from sqlalchemy.dialects.postgresql import insert

from app.core.database import get_async_db
from app.core.logger import get_logger
from app.models.stripe import StripePayment
from app.models.user import User
from app.models.admin_users import AdminUsers
from app.services.wallet_service import WalletService

logger = get_logger(name="webhooks")

router = APIRouter()

# Webhook signing secrets for verifying webhook authenticity
CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
CLERK_TENSORBLOCK_ORGANIZATION_ID = os.getenv("CLERK_TENSORBLOCK_ORGANIZATION_ID", "")

@router.post("/clerk")
async def clerk_webhook_handler(request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Handle Clerk webhooks for user events.

    Key events to handle:
    - organizationMembership.created: Add user to admin users table
    - organizationMembership.updated: Update user in admin users table
    - organizationMembership.deleted: Remove user from admin users table
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
        logger.info(f"Received Clerk webhook: {event_type}")

        if event_type == "organizationMembership.created" or event_type == "organizationMembership.updated":
            await handle_organization_membership_created(event_data, db)
        elif event_type == "organizationMembership.deleted":
            await handle_organization_membership_deleted(event_data, db)
        else:
            logger.warning(f"Unhandled Clerk event type: {event_type}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON payload", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.exception(f"Error processing Clerk webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}",
        )
    
    logger.info(f"Processed Clerk webhook: {event_type}")
    return {"status": "success", "message": f"Event {event_type} processed"}


async def handle_organization_membership_created(event_data: dict, db: AsyncSession):
    data = event_data['data']
    if data['organization']['id'] != CLERK_TENSORBLOCK_ORGANIZATION_ID:
        logger.warning(f"Received organization membership created event for non-TensorBlock organization: {data['organization']['id']}")
        return
    
    clerk_user_id = data['public_user_data']['user_id']
    role = data['role']
    if role != "org:admin":
        # delete from admin users table, if present
        await db.execute(delete(AdminUsers).where(AdminUsers.user_id.in_(select(User.id).where(User.clerk_user_id == clerk_user_id))))
    else:
        # insert into admin users table, if not already present
        await db.execute(insert(AdminUsers).from_select(['user_id'], select(User.id).where(User.clerk_user_id == clerk_user_id)).on_conflict_do_nothing())
    await db.commit()


async def handle_organization_membership_deleted(event_data: dict, db: AsyncSession):
    data = event_data['data']
    if data['organization']['id'] != CLERK_TENSORBLOCK_ORGANIZATION_ID:
        logger.warning(f"Received organization membership deleted event for non-TensorBlock organization: {data['organization']['id']}")
        return
    
    clerk_user_id = data['public_user_data']['user_id']
    # delete from admin users table, if present
    await db.execute(delete(AdminUsers).where(AdminUsers.user_id.in_(select(User.id).where(User.clerk_user_id == clerk_user_id))))
    await db.commit()


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
            update(StripePayment)
            .where(
                StripePayment.id == session_id,
                # Only update if the status is not completed
                StripePayment.status != "completed",
            )
            .values(
                status = status,
                amount = amount,
                currency = currency,
                raw_data = session,
            ).returning(StripePayment.user_id)
        )
        user_id = result.scalar_one_or_none()
        if not user_id:
            logger.warning(f"Updated stripe payment not found for session: {session_id} with status {status} and payment_status {payment_status}")
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
        
        result = await WalletService.adjust(
            db, 
            user_id, 
            amount_decimal, 
            f"deposit:stripe:{session_id}", 
            currency
        )
        assert result.get("success"), f"Failed to adjust wallet balance for user {user_id}: {result.get('reason')}"
        
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