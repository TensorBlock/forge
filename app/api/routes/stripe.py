import os
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import get_current_active_user_from_clerk, get_current_active_user
from app.api.schemas.stripe import CreateCheckoutSessionRequest
from app.models.user import User
from app.models.stripe import StripePayment
from app.core.database import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
import stripe
from app.core.logger import get_logger
from sqlalchemy import select
from fastapi import HTTPException

logger = get_logger(name="stripe")

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
stripe.api_key = STRIPE_API_KEY

router = APIRouter()

@router.post("/create-checkout-session/clerk")
async def stripe_create_checkout_session_clerk(request: Request, create_checkout_session_request: CreateCheckoutSessionRequest, user: User = Depends(get_current_active_user_from_clerk), db: AsyncSession = Depends(get_async_db)):
    return await stripe_create_checkout_session(request, create_checkout_session_request, user, db)


@router.post("/create-checkout-session")
async def stripe_create_checkout_session(request: Request, create_checkout_session_request: CreateCheckoutSessionRequest, user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)):
    """
    Create a checkout session for a user.
    """
    logger.info(f"Creating checkout session for user {user.id}")
    session = await stripe.checkout.Session.create_async(
        metadata={
            "user_id": user.id,
        },
        **create_checkout_session_request.model_dump(exclude_none=True),
    )
    stripe_payment = StripePayment(
        id=session.id,
        user_id=user.id,
        status=session.status,
        currency=session.currency.upper(),
        amount=session.amount_total,
        # store the whole session as raw_data
        raw_data=dict(session),
    )
    db.add(stripe_payment)
    await db.commit()

    return {
        'session_id': session.id,
        'url': session.url,
    }

@router.get("/checkout-session")
async def stripe_get_checkout_session(session_id: str, user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(
        select(
            StripePayment
        )
        .where(StripePayment.id == session_id, StripePayment.user_id == user.id)
    )
    stripe_payment = result.scalar_one_or_none()
    if not stripe_payment:
        raise HTTPException(status_code=404, detail="Stripe payment not found")

    return {
        'id': stripe_payment.id,
        'status': stripe_payment.status,
        'currency': stripe_payment.currency,
        'amount': stripe_payment.amount / 100.0 if stripe_payment.currency == "USD" else stripe_payment.amount,
        'created_at': stripe_payment.created_at,
        'updated_at': stripe_payment.updated_at,
    }

@router.get("/checkout-session/clerk")
async def stripe_get_checkout_session_clerk(session_id: str, user: User = Depends(get_current_active_user_from_clerk), db: AsyncSession = Depends(get_async_db)):
    return await stripe_get_checkout_session(session_id, user, db)
