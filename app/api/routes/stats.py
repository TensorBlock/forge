from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_active_user_from_clerk,
    get_current_user,
    get_async_db,
    get_user_by_api_key,
)
from app.models.user import User
from app.services.usage_stats_service import UsageStatsService

router = APIRouter()


# http://localhost:8000/stats/?start_date=2025-04-09&end_date=2025-04-09
# http://localhost:8000/stats/?model=gpt-3.5-turbo
@router.get("/", response_model=list[dict[str, Any]])
async def get_user_stats(
    current_user: User = Depends(get_user_by_api_key),
    provider: str | None = Query(None, description="Filter stats by provider name"),
    model: str | None = Query(None, description="Filter stats by model name"),
    start_date: date | None = Query(
        None, description="Start date for filtering (YYYY-MM-DD)"
    ),
    end_date: date | None = Query(
        None, description="End date for filtering (YYYY-MM-DD)"
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get aggregated usage statistics for the current user, queried from request logs.

    Allows filtering by provider, model, and date range (inclusive).
    """
    # Note: Service layer now handles aggregation and filtering
    # We pass the query parameters directly to the service method
    stats = await UsageStatsService.get_user_stats(
        db=db,
        user_id=current_user.id,
        provider=provider,
        model=model,
        start_date=start_date,
        end_date=end_date,
    )
    return stats


# http://localhost:8000/stats/clerk/?start_date=2025-04-09&end_date=2025-04-09
# http://localhost:8000/stats/clerk/?model=gpt-3.5-turbo
@router.get("/clerk", response_model=list[dict[str, Any]])
async def get_user_stats_clerk(
    current_user: User = Depends(get_current_active_user_from_clerk),
    provider: str | None = Query(None, description="Filter stats by provider name"),
    model: str | None = Query(None, description="Filter stats by model name"),
    start_date: date | None = Query(
        None, description="Start date for filtering (YYYY-MM-DD)"
    ),
    end_date: date | None = Query(
        None, description="End date for filtering (YYYY-MM-DD)"
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get aggregated usage statistics for the current user, queried from request logs.

    Allows filtering by provider, model, and date range (inclusive).
    """
    # Note: Service layer now handles aggregation and filtering
    # We pass the query parameters directly to the service method
    stats = await UsageStatsService.get_user_stats(
        db=db,
        user_id=current_user.id,
        provider=provider,
        model=model,
        start_date=start_date,
        end_date=end_date,
    )
    return stats


@router.get("/admin", response_model=list[dict[str, Any]])
async def get_all_stats(
    current_user: User = Depends(get_current_user),
    provider: str | None = Query(None, description="Filter stats by provider name"),
    model: str | None = Query(None, description="Filter stats by model name"),
    start_date: date | None = Query(
        None, description="Start date for filtering (YYYY-MM-DD)"
    ),
    end_date: date | None = Query(
        None, description="End date for filtering (YYYY-MM-DD)"
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get aggregated usage statistics for all users, queried from request logs.

    Only accessible to admin users. Allows filtering.
    """
    # Check if user is an admin
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=403, detail="Not authorized to access admin statistics"
        )

    stats = await UsageStatsService.get_all_stats(
        db=db, provider=provider, model=model, start_date=start_date, end_date=end_date
    )
    return stats
