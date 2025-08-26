from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.sql.functions import coalesce
from sqlalchemy import or_
from datetime import datetime, timedelta, UTC
from enum import StrEnum
import decimal

from app.api.dependencies import (
    get_async_db,
    get_current_active_user,
    get_current_active_user_from_clerk,
    get_user_by_api_key,
)
from app.models.user import User
from app.models.usage_tracker import UsageTracker
from app.models.provider_key import ProviderKey
from app.models.forge_api_key import ForgeApiKey
from app.api.schemas.statistic import (
    UsageRealtimeResponse,
    UsageSummaryResponse,
    ForgeKeysUsageSummaryResponse,
)

router = APIRouter()


# I want a query parameter called "offset: <int>" and "limit: <int>"
@router.get("/usage/realtime", response_model=list[UsageRealtimeResponse])
async def get_usage_realtime(
    current_user: User = Depends(get_user_by_api_key),
    db: AsyncSession = Depends(get_async_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    forge_key: str = Query(None, min_length=1),
    provider_name: str = Query(None, min_length=1),
    model_name: str = Query(None, min_length=1),
    started_at: datetime = Query(None),
    ended_at: datetime = Query(None),
):
    """
    Get real-time usage statistics for the current user up to the last 7 days.
    """
    # Calculate the date 7 days ago
    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)
    started_at = (
        started_at
        if started_at is not None and started_at > seven_days_ago
        else seven_days_ago
    )
    ended_at = ended_at if ended_at is not None and ended_at < now else None

    # Build the query
    query = (
        select(
            UsageTracker.created_at.label("timestamp"),
            coalesce(ForgeApiKey.name, ForgeApiKey.key).label("forge_key"),
            ProviderKey.provider_name.label("provider_name"),
            UsageTracker.model.label("model_name"),
            (UsageTracker.input_tokens + UsageTracker.output_tokens).label("tokens"),
            (UsageTracker.input_tokens - UsageTracker.cached_tokens).label(
                "input_tokens"
            ),
            UsageTracker.output_tokens.label("output_tokens"),
            UsageTracker.cached_tokens.label("cached_tokens"),
            UsageTracker.cost.label("cost"),
            func.extract(
                "epoch", UsageTracker.updated_at - UsageTracker.created_at
            ).label("duration"),
        )
        .join(ProviderKey, UsageTracker.provider_key_id == ProviderKey.id)
        .join(ForgeApiKey, UsageTracker.forge_key_id == ForgeApiKey.id)
        .where(
            UsageTracker.user_id == current_user.id,
            UsageTracker.created_at >= started_at,
            ended_at is None or UsageTracker.created_at <= ended_at,
            forge_key is None
            or or_(
                ForgeApiKey.key.ilike(f"%{forge_key}%"),
                ForgeApiKey.name.ilike(f"%{forge_key}%"),
            ),
            provider_name is None
            or ProviderKey.provider_name.ilike(f"%{provider_name}%"),
            model_name is None or UsageTracker.model.ilike(f"%{model_name}%"),
            UsageTracker.updated_at.is_not(None),
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
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "cached_tokens": row.cached_tokens,
                "cost": decimal.Decimal(row.cost).normalize(),
                "duration": round(float(row.duration), 2)
                if row.duration is not None
                else 0.0,
            }
        )
    return [UsageRealtimeResponse(**usage_stat) for usage_stat in usage_stats]


@router.get("/usage/realtime/clerk", response_model=list[UsageRealtimeResponse])
async def get_usage_realtime_clerk(
    current_user: User = Depends(get_current_active_user_from_clerk),
    db: AsyncSession = Depends(get_async_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    forge_key: str = Query(None, min_length=1),
    provider_name: str = Query(None, min_length=1),
    model_name: str = Query(None, min_length=1),
    started_at: datetime = Query(None),
    ended_at: datetime = Query(None),
):
    return await get_usage_realtime(
        current_user,
        db,
        offset,
        limit,
        forge_key,
        provider_name,
        model_name,
        started_at,
        ended_at,
    )


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
            func.sum(UsageTracker.input_tokens - UsageTracker.cached_tokens).label(
                "input_tokens"
            ),
            func.sum(UsageTracker.output_tokens).label("output_tokens"),
            func.sum(UsageTracker.cached_tokens).label("cached_tokens"),
            func.sum(UsageTracker.cost).label("cost"),
        )
        .join(ForgeApiKey, UsageTracker.forge_key_id == ForgeApiKey.id)
        .where(
            UsageTracker.user_id == current_user.id,
            UsageTracker.created_at >= start_time,
            UsageTracker.updated_at.is_not(None),
        )
        .group_by(time_group, ForgeApiKey.name, ForgeApiKey.key)
        .order_by(time_group, desc("cost"), "forge_key")
    )

    # Execute the query
    result = await db.execute(query)
    rows = result.fetchall()

    data_points = dict()
    for row in rows:
        if row.time_point not in data_points:
            data_points[row.time_point] = {
                "breakdown": [],
                "total_tokens": 0,
                "total_cost": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cached_tokens": 0,
            }
        data_points[row.time_point]["breakdown"].append(
            {
                "forge_key": row.forge_key,
                "tokens": row.tokens,
                "cost": decimal.Decimal(row.cost).normalize(),
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "cached_tokens": row.cached_tokens,
            }
        )
        data_points[row.time_point]["total_tokens"] += row.tokens
        data_points[row.time_point]["total_cost"] += decimal.Decimal(
            row.cost
        ).normalize()
        data_points[row.time_point]["total_input_tokens"] += row.input_tokens
        data_points[row.time_point]["total_output_tokens"] += row.output_tokens
        data_points[row.time_point]["total_cached_tokens"] += row.cached_tokens

    return [
        UsageSummaryResponse(
            time_point=time_point,
            breakdown=data_point["breakdown"],
            total_tokens=data_point["total_tokens"],
            total_cost=data_point["total_cost"],
            total_input_tokens=data_point["total_input_tokens"],
            total_output_tokens=data_point["total_output_tokens"],
            total_cached_tokens=data_point["total_cached_tokens"],
        )
        for time_point, data_point in data_points.items()
    ]


@router.get("/usage/summary/clerk", response_model=list[UsageSummaryResponse])
async def get_usage_summary_clerk(
    current_user: User = Depends(get_current_active_user_from_clerk),
    db: AsyncSession = Depends(get_async_db),
    span: UsageSummaryTimeSpan = Query(UsageSummaryTimeSpan.week),
):
    return await get_usage_summary(current_user, db, span)


class ForgeKeysUsageTimeSpan(StrEnum):
    day = "day"
    week = "week"
    month = "month"
    year = "year"
    all = "all"


@router.get("/forge-keys/usage", response_model=list[ForgeKeysUsageSummaryResponse])
async def get_forge_keys_usage(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    span: ForgeKeysUsageTimeSpan = Query(ForgeKeysUsageTimeSpan.week),
):
    """
    Get usage summary for all the forge keys for the past day/week/month/year/all
    """
    start_time = None
    if span == ForgeKeysUsageTimeSpan.day:
        start_time = datetime.now(UTC) - timedelta(days=1)
    elif span == ForgeKeysUsageTimeSpan.week:
        start_time = datetime.now(UTC) - timedelta(weeks=1)
    elif span == ForgeKeysUsageTimeSpan.month:
        start_time = datetime.now(UTC) - timedelta(days=30)
    elif span == ForgeKeysUsageTimeSpan.year:
        start_time = datetime.now(UTC) - timedelta(days=365)

    query = (
        select(
            coalesce(ForgeApiKey.name, ForgeApiKey.key).label("forge_key"),
            func.sum(UsageTracker.input_tokens + UsageTracker.output_tokens).label(
                "tokens"
            ),
            func.sum(UsageTracker.input_tokens - UsageTracker.cached_tokens).label(
                "input_tokens"
            ),
            func.sum(UsageTracker.output_tokens).label("output_tokens"),
            func.sum(UsageTracker.cached_tokens).label("cached_tokens"),
            func.sum(UsageTracker.cost).label("cost"),
        )
        .join(ForgeApiKey, UsageTracker.forge_key_id == ForgeApiKey.id)
        .where(
            UsageTracker.user_id == current_user.id,
            start_time is None or UsageTracker.created_at >= start_time,
            UsageTracker.updated_at.is_not(None),
        )
        .group_by(ForgeApiKey.name, ForgeApiKey.key)
        .order_by(desc("cost"), "forge_key")
    )

    result = await db.execute(query)
    rows = result.fetchall()

    return [
        ForgeKeysUsageSummaryResponse(
            forge_key=row.forge_key,
            tokens=row.tokens,
            cost=decimal.Decimal(row.cost).normalize(),
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cached_tokens=row.cached_tokens,
        )
        for row in rows
    ]


@router.get(
    "/forge-keys/usage/clerk", response_model=list[ForgeKeysUsageSummaryResponse]
)
async def get_forge_keys_usage_clerk(
    current_user: User = Depends(get_current_active_user_from_clerk),
    db: AsyncSession = Depends(get_async_db),
    span: ForgeKeysUsageTimeSpan = Query(ForgeKeysUsageTimeSpan.week),
):
    return await get_forge_keys_usage(current_user, db, span)
