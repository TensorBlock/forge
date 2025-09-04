from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List
from datetime import datetime

from app.api.dependencies import get_current_active_user, get_current_active_user_from_clerk
from app.core.database import get_async_db
from app.models.user import User
from app.models.stripe import StripePayment
from app.services.wallet_service import WalletService
from sqlalchemy import select, desc

router = APIRouter()

class WalletResponse(BaseModel):
    balance: Decimal
    blocked: bool
    currency: str

@router.get("/balance", response_model=WalletResponse)
async def get_wallet_balance(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get current wallet balance"""
    wallet = await WalletService.get(db, user.id)
    
    if not wallet:
        await WalletService.ensure_wallet(db, user.id)
        return WalletResponse(balance=Decimal("0"), blocked=False, currency="USD")
    
    return WalletResponse(**wallet)

@router.get("/balance/clerk", response_model=WalletResponse)
async def get_wallet_balance_clerk(
    user: User = Depends(get_current_active_user_from_clerk),
    db: AsyncSession = Depends(get_async_db)
):
    return await get_wallet_balance(user, db)

class TransactionResponse(BaseModel):
    currency: str
    amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

@router.get("/transactions/history", response_model=List[TransactionResponse])
async def get_wallet_transactions_history(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
):
    query = (
        select(
            StripePayment.currency,
            StripePayment.amount,
            StripePayment.status,
            StripePayment.created_at,
            StripePayment.updated_at,
        )
        .where(StripePayment.user_id == user.id, StripePayment.status == "completed")
        .order_by(desc(StripePayment.updated_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    transactions = result.fetchall()
    return [TransactionResponse(
        currency=transaction.currency,
        # Convert cents to dollars for USD
        amount=transaction.amount / 100.0 if transaction.currency == "USD" else transaction.amount,
        status=transaction.status,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    ) for transaction in transactions]

@router.get("/transactions/history/clerk", response_model=List[TransactionResponse])
async def get_wallet_transactions_history_clerk(
    user: User = Depends(get_current_active_user_from_clerk),
    db: AsyncSession = Depends(get_async_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
):
    return await get_wallet_transactions_history(user, db, offset, limit)
