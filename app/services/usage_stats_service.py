from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.api_request_log import ApiRequestLog

logger = get_logger(name="usage_stats")


class UsageStatsService:
    """Service for managing usage statistics"""

    @staticmethod
    async def log_api_request(
        db: AsyncSession,
        user_id: int | None,
        provider_name: str,
        model: str,
        endpoint: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        """Logs a single API request into the api_request_log table."""
        try:
            total_tokens = input_tokens + output_tokens
            log_entry = ApiRequestLog(
                user_id=user_id,
                provider_name=provider_name,
                model=model,
                endpoint=endpoint,
                request_timestamp=datetime.utcnow(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
            )
            db.add(log_entry)
            await db.commit()
            logger.debug(
                f"Logged API request for user {user_id}: {provider_name}/{model}/{endpoint}"
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to log API request for user {user_id}: {e}", exc_info=True
            )

    @staticmethod
    async def get_user_stats(
        db: AsyncSession,
        user_id: int,
        provider: str | None = None,
        model: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get aggregated usage statistics for a user, queried from ApiRequestLog.

        Allows filtering by provider, model, and date range.
        """
        logger.info(f"Getting usage stats for user {user_id} from ApiRequestLog")

        query = select(
            ApiRequestLog.provider_name,
            ApiRequestLog.model,
            func.sum(ApiRequestLog.input_tokens).label("input_tokens"),
            func.sum(ApiRequestLog.output_tokens).label("output_tokens"),
            func.sum(ApiRequestLog.total_tokens).label("total_tokens"),
            func.count(ApiRequestLog.id).label("requests_count"),
            func.sum(ApiRequestLog.cost).label("cost"),
        ).filter(ApiRequestLog.user_id == user_id)

        if provider:
            query = query.filter(ApiRequestLog.provider_name == provider)
        if model:
            query = query.filter(ApiRequestLog.model == model)
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.filter(ApiRequestLog.request_timestamp >= start_datetime)
        if end_date:
            end_datetime = datetime.combine(
                end_date + timedelta(days=1), datetime.min.time()
            )
            query = query.filter(ApiRequestLog.request_timestamp < end_datetime)

        query = query.group_by(ApiRequestLog.provider_name, ApiRequestLog.model)

        results = await db.execute(query)

        return [
            {
                "provider_name": row.provider_name,
                "model": row.model,
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "total_tokens": row.total_tokens or 0,
                "requests_count": row.requests_count or 0,
                "cost": row.cost or 0.0,
            }
            for row in results
        ]

    @staticmethod
    async def get_all_stats(
        db: AsyncSession,
        provider: str | None = None,  # Add provider filter
        model: str | None = None,  # Add model filter
        start_date: date | None = None,  # Add start_date filter
        end_date: date | None = None,  # Add end_date filter
    ) -> list[dict[str, Any]]:
        """Get aggregated usage statistics for ALL users, queried from ApiRequestLog.

        Allows filtering by provider, model, and date range.
        """
        logger.info("Getting usage stats for ALL users from ApiRequestLog")

        query = select(
            ApiRequestLog.provider_name,
            ApiRequestLog.model,
            func.sum(ApiRequestLog.input_tokens).label("input_tokens"),
            func.sum(ApiRequestLog.output_tokens).label("output_tokens"),
            func.sum(ApiRequestLog.total_tokens).label("total_tokens"),
            func.count(ApiRequestLog.id).label(
                "requests_count"
            ),  # Count rows for requests
            func.sum(ApiRequestLog.cost).label("cost"),
        )  # No initial user_id filter

        # Apply filters
        if provider:
            query = query.filter(ApiRequestLog.provider_name == provider)
        if model:
            query = query.filter(ApiRequestLog.model == model)
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.filter(ApiRequestLog.request_timestamp >= start_datetime)
        if end_date:
            end_datetime = datetime.combine(
                end_date + timedelta(days=1), datetime.min.time()
            )
            query = query.filter(ApiRequestLog.request_timestamp < end_datetime)

        # Group results (could group by user_id as well if needed)
        query = query.group_by(ApiRequestLog.provider_name, ApiRequestLog.model)

        # Execute query
        results = await db.execute(query)

        # Convert results to dictionaries
        return [
            {
                "provider_name": row.provider_name,
                "model": row.model,
                "input_tokens": row.input_tokens or 0,  # Handle potential None from sum
                "output_tokens": row.output_tokens or 0,
                "total_tokens": row.total_tokens or 0,
                "requests_count": row.requests_count or 0,
                "cost": row.cost or 0.0,
            }
            for row in results
        ]
