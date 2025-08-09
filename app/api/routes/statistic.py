from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.sql.functions import coalesce
from datetime import datetime, timedelta, UTC
from enum import StrEnum

from app.api.dependencies import get_async_db, get_current_active_user
from app.models.user import User
from app.models.usage_tracker import UsageTracker
from app.models.provider_key import ProviderKey
from app.models.forge_api_key import ForgeApiKey
from app.api.schemas.statistic import (
    UsageRealtimeResponse,
    UsageSummaryResponse,
    ForgeKeyUsageSummaryResponse,
)

router = APIRouter()


# I want a query parameter called "offset: <int>" and "limit: <int>"
@router.get("/usage/realtime", response_model=list[UsageRealtimeResponse])
async def get_usage_realtime(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
):
    """
    Get real-time usage statistics for the current user up to the last 7 days.
    """
    # Calculate the date 7 days ago
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    # Build the query
    query = (
        select(
            UsageTracker.created_at.label("timestamp"),
            coalesce(ForgeApiKey.name, ForgeApiKey.key).label("forge_key"),
            ProviderKey.provider_name.label("provider_name"),
            UsageTracker.model.label("model_name"),
            (UsageTracker.input_tokens + UsageTracker.output_tokens).label("tokens"),
            func.extract(
                "epoch", UsageTracker.updated_at - UsageTracker.created_at
            ).label("duration"),
        )
        .join(ProviderKey, UsageTracker.provider_key_id == ProviderKey.id)
        .join(ForgeApiKey, UsageTracker.forge_key_id == ForgeApiKey.id)
        .where(
            UsageTracker.user_id == current_user.id,
            UsageTracker.created_at >= seven_days_ago,
        )
        .order_by(desc(UsageTracker.created_at))
        .offset(offset)
        .limit(limit)
    )

    # Execute the query
    result = await db.execute(query)
    rows = result.fetchall()

    # Convert to list of dictionaries
    usage_stats = []
    for row in rows:
        usage_stats.append(
            {
                "timestamp": row.timestamp,
                "forge_key": row.forge_key,
                "provider_name": row.provider_name,
                "model_name": row.model_name,
                "tokens": row.tokens,
                "duration": round(float(row.duration), 2)
                if row.duration is not None
                else 0.0,
            }
        )
    print(usage_stats)

    return [UsageRealtimeResponse(**usage_stat) for usage_stat in usage_stats]


class UsageSummaryTimeSpan(StrEnum):
    day = "day"
    week = "week"
    month = "month"


@router.get("/usage/summary", response_model=list[UsageSummaryResponse])
async def get_usage_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    span: UsageSummaryTimeSpan = Query(UsageSummaryTimeSpan.week),
):
    """
    Get usage summary for the current user for the past day/week/month
    """
    start_time = None
    if span == UsageSummaryTimeSpan.day:
        start_time = datetime.now(UTC) - timedelta(days=1)
    elif span == UsageSummaryTimeSpan.week:
        start_time = datetime.now(UTC) - timedelta(weeks=1)
    elif span == UsageSummaryTimeSpan.month:
        start_time = datetime.now(UTC) - timedelta(days=30)

    # Build the query based on time span
    if span == UsageSummaryTimeSpan.day:
        # For daily span, group by hour
        time_group = func.date_trunc("hour", UsageTracker.created_at)
    else:
        # For weekly/monthly span, group by day
        time_group = func.date_trunc("day", UsageTracker.created_at)

    query = (
        select(
            time_group.label("time_point"),
            coalesce(ForgeApiKey.name, ForgeApiKey.key).label("forge_key"),
            func.sum(UsageTracker.input_tokens + UsageTracker.output_tokens).label(
                "tokens"
            ),
        )
        .join(ForgeApiKey, UsageTracker.forge_key_id == ForgeApiKey.id)
        .where(
            UsageTracker.user_id == current_user.id,
            UsageTracker.created_at >= start_time,
        )
        .group_by(time_group, ForgeApiKey.name, ForgeApiKey.key)
        .order_by(time_group, desc("tokens"), "forge_key")
    )

    # Execute the query
    result = await db.execute(query)
    rows = result.fetchall()

    data_points = dict()
    for row in rows:
        if row.time_point not in data_points:
            data_points[row.time_point] = {"breakdown": [], "total_tokens": 0}
        data_points[row.time_point]["breakdown"].append(
            {"forge_key": row.forge_key, "tokens": row.tokens}
        )
        data_points[row.time_point]["total_tokens"] += row.tokens

    return [
        UsageSummaryResponse(
            time_point=time_point,
            breakdown=data_point["breakdown"],
            total_tokens=data_point["total_tokens"],
        )
        for time_point, data_point in data_points.items()
    ]


class ForgeKeyUsageTimeSpan(StrEnum):
    day = "day"
    week = "week"
    month = "month"
    year = "year"
    all = "all"


@router.get("/forge-key/usage", response_model=list[ForgeKeyUsageSummaryResponse])
async def get_forge_key_usage(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    span: ForgeKeyUsageTimeSpan = Query(ForgeKeyUsageTimeSpan.week),
):
    """
    Get usage summary for all the forge keys for the past day/week/month/year/all
    """
    start_time = None
    if span == ForgeKeyUsageTimeSpan.day:
        start_time = datetime.now(UTC) - timedelta(days=1)
    elif span == ForgeKeyUsageTimeSpan.week:
        start_time = datetime.now(UTC) - timedelta(weeks=1)
    elif span == ForgeKeyUsageTimeSpan.month:
        start_time = datetime.now(UTC) - timedelta(days=30)
    elif span == ForgeKeyUsageTimeSpan.year:
        start_time = datetime.now(UTC) - timedelta(days=365)

    query = (
        select(
            coalesce(ForgeApiKey.name, ForgeApiKey.key).label("forge_key"),
            func.sum(UsageTracker.input_tokens + UsageTracker.output_tokens).label(
                "tokens"
            ),
        )
        .join(ForgeApiKey, UsageTracker.forge_key_id == ForgeApiKey.id)
        .where(
            UsageTracker.user_id == current_user.id,
            start_time is None or UsageTracker.created_at >= start_time,
        )
        .group_by(ForgeApiKey.name, ForgeApiKey.key)
        .order_by(desc("tokens"), "forge_key")
    )

    result = await db.execute(query)
    rows = result.fetchall()

    return [
        ForgeKeyUsageSummaryResponse(forge_key=row.forge_key, tokens=row.tokens)
        for row in rows
    ]
