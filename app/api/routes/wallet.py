from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.dependencies import get_current_active_user, get_current_active_user_from_clerk
from app.core.database import get_async_db
from app.models.user import User
from app.services.wallet_service import WalletService

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
