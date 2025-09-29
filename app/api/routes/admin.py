from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from decimal import Decimal
from pydantic import BaseModel
import uuid

from app.api.dependencies import get_current_active_admin_user_from_clerk
from app.core.database import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.stripe import StripePayment
from app.core.logger import get_logger
from app.api.schemas.admin import AddBalanceRequest
from app.services.wallet_service import WalletService

logger = get_logger(name="admin")
router = APIRouter()

class AddBalanceResponse(BaseModel):
    balance: Decimal
    blocked: bool


@router.post("/add-balance")
async def add_balance(
    add_balance_request: AddBalanceRequest,
    current_user: User = Depends(get_current_active_admin_user_from_clerk),
    db: AsyncSession = Depends(get_async_db),
):
    """Add balance to a user"""
    user_id = add_balance_request.user_id
    email = add_balance_request.email
    amount = add_balance_request.amount

    result = await db.execute(
        select(User)
        .where(
            user_id is None or User.id == user_id,
            email is None or User.email == email,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    amount_decimal = Decimal(amount / 100.0)
    result = await WalletService.adjust(db, user.id, amount_decimal, f"Admin {current_user.id} added balance for user {user.id}")
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=f"Failed to add balance for user {user.id}: {result.get('reason')}")

    # add the amount to the user's stripe payment
    stripe_payment = StripePayment(
        id=f"tb_admin_{uuid.uuid4().hex}",
        user_id=user.id,
        amount=amount,
        currency="USD",
        status="completed",
        raw_data={"reason": f"Admin {current_user.id} added balance for user {user.id}"},
    )
    db.add(stripe_payment)
    await db.commit()
    logger.info(f"Added balance {amount_decimal} for user {user.id} by admin {current_user.id}")

    return AddBalanceResponse(balance=result.get("balance"), blocked=result.get("blocked"))
