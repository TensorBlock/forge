from datetime import datetime, UTC
from typing import Dict, Optional
from decimal import Decimal
import asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.logger import get_logger
from app.models.wallet import Wallet
from app.models.provider_key import ProviderKey

logger = get_logger(name="wallet_service")

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_MS = 10  # milliseconds

class WalletService:
    @staticmethod
    async def ensure_wallet(db: AsyncSession, account_id: int) -> None:
        """Create wallet if it doesn't exist"""
        try:
            result = await db.execute(select(Wallet).filter(Wallet.account_id == account_id))
            if result.scalar_one_or_none() is None:
                wallet = Wallet(account_id=account_id)
                db.add(wallet)
                await db.commit()
                logger.debug(f"Created wallet for account {account_id}")
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to ensure wallet for account {account_id}: {e}")
            raise

    @staticmethod
    async def precheck(db: AsyncSession, account_id: int) -> Dict[str, any]:
        """Check if user can make requests"""
        try:
            result = await db.execute(select(Wallet).filter(Wallet.account_id == account_id))
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                await WalletService.ensure_wallet(db, account_id)
                return {"blocked": False, "balance": Decimal("0"), "allowed": False}
            
            allowed = not wallet.blocked and wallet.balance > 0
            return {
                "blocked": wallet.blocked,
                "balance": wallet.balance,
                "allowed": allowed
            }
        except Exception as e:
            logger.exception(f"Precheck failed for account {account_id}: {e}")
            raise

    @staticmethod
    async def adjust(
        db: AsyncSession, 
        account_id: int, 
        delta: Decimal, 
        reason: str, 
        currency: str = "USD"
    ) -> Dict[str, any]:
        """Adjust wallet balance with optimistic locking and retry"""
        for attempt in range(MAX_RETRIES):
            try:
                # Read current wallet state including version
                result = await db.execute(select(Wallet).where(Wallet.account_id == account_id))
                wallet = result.scalar_one_or_none()
                
                if not wallet:
                    await WalletService.ensure_wallet(db, account_id)
                    continue  # Retry after creating wallet
                
                current_version = wallet.version
                
                # Attempt optimistic update - always allow deductions (oversubscription is OK)
                stmt = update(Wallet).where(
                    (Wallet.account_id == account_id) &
                    (Wallet.version == current_version)
                ).values(
                    balance=Wallet.balance + delta,
                    updated_at=datetime.now(UTC),
                    version=Wallet.version + 1
                ).returning(Wallet.balance, Wallet.blocked)
                
                result = await db.execute(stmt)
                row = result.fetchone()
                
                if row is None:
                    # Version conflict - another process updated first
                    if attempt < MAX_RETRIES - 1:
                        await db.rollback()
                        await asyncio.sleep(RETRY_DELAY_MS / 1000.0)
                        logger.debug(f"Optimistic lock conflict for account {account_id}, retrying ({attempt + 1}/{MAX_RETRIES})")
                        continue
                    else:
                        await db.rollback()
                        logger.warning(f"Max retries exceeded for account {account_id} adjustment")
                        return {"success": False, "reason": "version_conflict"}
                
                await db.commit()
                logger.debug(f"Adjusted balance for account {account_id} by {delta} ({reason}) after {attempt + 1} attempts")
                return {"success": True, "balance": row[0], "blocked": row[1]}
                
            except Exception as e:
                await db.rollback()
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Error adjusting balance for account {account_id}, retrying: {e}")
                    await asyncio.sleep(RETRY_DELAY_MS / 1000.0)
                    continue
                else:
                    logger.error(f"Failed to adjust balance for account {account_id} after {MAX_RETRIES} attempts: {e}")
                    raise
        
        return {"success": False, "reason": "max_retries_exceeded"}

    @staticmethod
    async def set_blocked(db: AsyncSession, account_id: int, blocked: bool) -> None:
        """Block or unblock account with optimistic locking"""
        for attempt in range(MAX_RETRIES):
            try:
                # Read current version
                result = await db.execute(select(Wallet).where(Wallet.account_id == account_id))
                wallet = result.scalar_one_or_none()
                
                if not wallet:
                    logger.warning(f"Wallet not found for account {account_id}")
                    return
                
                current_version = wallet.version
                
                # Update with version check
                result = await db.execute(
                    update(Wallet).where(
                        (Wallet.account_id == account_id) &
                        (Wallet.version == current_version)
                    ).values(
                        blocked=blocked,
                        updated_at=datetime.now(UTC),
                        version=Wallet.version + 1
                    )
                )
                
                if result.rowcount == 0:
                    # Version conflict
                    if attempt < MAX_RETRIES - 1:
                        await db.rollback()
                        await asyncio.sleep(RETRY_DELAY_MS / 1000.0)
                        logger.debug(f"Optimistic lock conflict setting blocked status for account {account_id}, retrying")
                        continue
                    else:
                        await db.rollback()
                        logger.warning(f"Failed to set blocked status after {MAX_RETRIES} attempts for account {account_id}")
                        return
                
                await db.commit()
                logger.debug(f"Set blocked={blocked} for account {account_id} after {attempt + 1} attempts")
                return
                
            except Exception as e:
                await db.rollback()
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Error setting blocked status for account {account_id}, retrying: {e}")
                    await asyncio.sleep(RETRY_DELAY_MS / 1000.0)
                    continue
                else:
                    logger.error(f"Failed to set blocked status for account {account_id} after {MAX_RETRIES} attempts: {e}")
                    raise

    @staticmethod
    async def get(db: AsyncSession, account_id: int) -> Optional[Dict[str, any]]:
        """Get wallet details"""
        try:
            result = await db.execute(select(Wallet).filter(Wallet.account_id == account_id))
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                return None
            
            return {
                "balance": wallet.balance,
                "blocked": wallet.blocked,
                "currency": wallet.currency
            }
        except Exception as e:
            logger.error(f"Failed to get wallet for account {account_id}: {e}")
            raise
    
    # -------------------------------------------------------------
    # Helper: perform wallet precheck
    # -------------------------------------------------------------
    @staticmethod
    async def wallet_precheck(user_id: int, db: AsyncSession, provider_key_id: int) -> None:
        """Check wallet balance and ensure user can make requests"""
        provider_key = await db.execute(select(ProviderKey).filter(ProviderKey.id == provider_key_id))
        provider_key = provider_key.scalar_one_or_none()
        # If the provider key is not billable, we don't need to check the wallet
        if not provider_key or not provider_key.billable:
            return

        await WalletService.ensure_wallet(db, user_id)
        check_result = await WalletService.precheck(db, user_id)
        
        if not check_result["allowed"]:
            if check_result["blocked"]:
                raise HTTPException(status_code=402, detail="Account blocked")
            else:
                raise HTTPException(status_code=402, detail="Insufficient balance")