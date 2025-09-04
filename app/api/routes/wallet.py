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
from app.models.usage_tracker import UsageTracker
from app.services.wallet_service import WalletService
from sqlalchemy import select, desc, func

router = APIRouter()

class WalletResponse(BaseModel):
    balance: Decimal
    blocked: bool
    currency: str
    total_spent: Decimal
    total_earned: Decimal

@router.get("/balance", response_model=WalletResponse)
async def get_wallet_balance(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get current wallet balance"""
    wallet = await WalletService.get(db, user.id)
    
    if not wallet:
        await WalletService.ensure_wallet(db, user.id)
        return WalletResponse(balance=Decimal("0"), blocked=False, currency="USD", total_spent=Decimal("0"), total_earned=Decimal("0"))
    
    result = await db.execute(select(func.sum(UsageTracker.cost)).where(UsageTracker.user_id == user.id, UsageTracker.updated_at.is_not(None)))
    total_spent = result.scalar_one_or_none() or "0"
    result = await db.execute(select(func.sum(StripePayment.amount)).where(StripePayment.user_id == user.id, StripePayment.status == "completed"))
    total_earned = result.scalar_one_or_none() or "0"
    
    return WalletResponse(**wallet, total_spent=Decimal(total_spent), total_earned=Decimal(total_earned))

@router.get("/balance/clerk", response_model=WalletResponse)
async def get_wallet_balance_clerk(
    user: User = Depends(get_current_active_user_from_clerk),
    db: AsyncSession = Depends(get_async_db)
):
    return await get_wallet_balance(user, db)

class TransactionHistoryItem(BaseModel):
    currency: str
    amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

class TransactionHistoryResponse(BaseModel):
    items: List[TransactionHistoryItem]
    total: int
    page_size: int
    page_index: int

@router.get("/transactions/history", response_model=TransactionHistoryResponse)
async def get_wallet_transactions_history(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    page_size: int = Query(10, ge=1),
    page_index: int = Query(0, ge=0),
    status: str = Query(None, min_length=1),
    started_at: datetime = Query(None),
):
    # I would also want to get the total count of the transactions within one sql query
    query = (
        select(
            StripePayment.currency,
            StripePayment.amount,
            StripePayment.status,
            StripePayment.created_at,
            StripePayment.updated_at,
            func.count().over().label("total"),
        )
        .where(StripePayment.user_id == user.id, status is None or StripePayment.status == status, started_at is None or StripePayment.created_at >= started_at)
        .order_by(desc(StripePayment.updated_at))
        .offset(page_index * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    transactions = result.fetchall()
    return TransactionHistoryResponse(
        items=[
            TransactionHistoryItem(
                currency=transaction.currency,
                # Convert cents to dollars for USD
                amount=transaction.amount / 100.0 if transaction.currency == "USD" else transaction.amount,
                status=transaction.status,
                created_at=transaction.created_at,
                updated_at=transaction.updated_at,
            )
        for transaction in transactions],
        total=transactions[0].total if transactions else 0,
        page_size=page_size,
        page_index=page_index,
    )

@router.get("/transactions/history/clerk", response_model=TransactionHistoryResponse)
async def get_wallet_transactions_history_clerk(
    user: User = Depends(get_current_active_user_from_clerk),
    db: AsyncSession = Depends(get_async_db),
    page_size: int = Query(10, ge=1),
    page_index: int = Query(0, ge=0),
    status: str = Query(None, min_length=1),
    started_at: datetime = Query(None),
):
    return await get_wallet_transactions_history(user, db, page_size, page_index, status, started_at)
