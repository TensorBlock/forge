from datetime import UTC
from datetime import datetime
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlalchemy import select
import uuid

from app.core.logger import get_logger
from app.models.usage_tracker import UsageTracker
from app.services.pricing_service import PricingService

logger = get_logger(name="usage_tracker")

class UsageTrackerService:
    """Service for tracking usage of providers and forge API keys."""
    @staticmethod
    async def start_tracking_usage(
        db: AsyncSession,
        user_id: int,
        provider_key_id: int,
        forge_key_id: int,
        model: str,
        endpoint: str,
    ) -> int:
        try:
            usage_tracker = UsageTracker(
                user_id=user_id,
                provider_key_id=provider_key_id,
                forge_key_id=forge_key_id,
                model=model,
                endpoint=endpoint,
                created_at=datetime.now(UTC),
            )
            db.add(usage_tracker)
            await db.commit()
            logger.debug(f"Started tracking usage for user {user_id} with provider {provider_key_id} and forge {forge_key_id} for model {model} and endpoint {endpoint}")
            # return the id of the usage tracker
            return usage_tracker.id
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to track usage: {e}")
    
    @staticmethod
    async def update_usage_tracker(
        db: AsyncSession,
        usage_tracker_id: uuid.UUID,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
        reasoning_tokens: int,
    ) -> None:
        if usage_tracker_id is None:
            return

        try:
            result = await db.execute(
                select(UsageTracker)
                .options(selectinload(UsageTracker.provider_key))
                .filter(UsageTracker.id == usage_tracker_id)
            )
            usage_tracker = result.scalar_one_or_none()
            now = datetime.now(UTC)
            logger.info(f"provider_key: {usage_tracker.provider_key.provider_name}")
            price_info = await PricingService.calculate_usage_cost(
                db,
                usage_tracker.provider_key.provider_name.lower(),
                usage_tracker.model.lower(),
                input_tokens,
                output_tokens,
                cached_tokens,
                now,
            )
            usage_tracker.input_tokens = input_tokens
            usage_tracker.output_tokens = output_tokens
            usage_tracker.cached_tokens = cached_tokens
            usage_tracker.updated_at = now
            usage_tracker.cost = price_info['total_cost']
            usage_tracker.currency = price_info['currency']
            usage_tracker.pricing_source = price_info['pricing_source']
            await db.commit()
            logger.debug(f"Updated usage tracker {usage_tracker_id} with input_tokens {input_tokens}, output_tokens {output_tokens}, cached_tokens {cached_tokens}, reasoning_tokens {reasoning_tokens}")
        except NoResultFound:
            logger.error(f"Usage tracker not found: {usage_tracker_id}")
        except Exception as e:
            await db.rollback()
            logger.exception(f"Failed to update usage tracker: {e}")

    @staticmethod
    async def delete_usage_tracker_record(
        db: AsyncSession,
        usage_tracker_id: uuid.UUID,
    ) -> None:
        if usage_tracker_id is None:
            return
        
        try:
            await db.execute(delete(UsageTracker).where(UsageTracker.id == usage_tracker_id))
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete usage tracker record: {e}")