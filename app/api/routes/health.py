"""
Health check and monitoring endpoints for production deployments.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.database import get_connection_info, get_db_session
from app.core.logger import get_logger

logger = get_logger(name="health")
router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 if the service is running.
    """
    return {"status": "healthy", "service": "forge"}


@router.get("/health/database")
async def database_health_check():
    """
    Database health check endpoint.
    Returns detailed information about database connectivity and pool status.
    """
    try:
        # Test database connection
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        
        # Get connection pool information
        pool_info = get_connection_info()
        
        # Calculate connection usage
        sync_pool = pool_info['sync_engine']
        async_pool = pool_info['async_engine']
        
        sync_usage = sync_pool['checked_out'] / (pool_info['pool_size'] + pool_info['max_overflow']) * 100
        async_usage = async_pool['checked_out'] / (pool_info['pool_size'] + pool_info['max_overflow']) * 100
        
        return {
            "status": "healthy",
            "database": "connected",
            "connection_pools": {
                "sync": {
                    "checked_out": sync_pool['checked_out'],
                    "checked_in": sync_pool['checked_in'],
                    "size": sync_pool['size'],
                    "usage_percent": round(sync_usage, 1)
                },
                "async": {
                    "checked_out": async_pool['checked_out'],
                    "checked_in": async_pool['checked_in'], 
                    "size": async_pool['size'],
                    "usage_percent": round(async_usage, 1)
                }
            },
            "configuration": {
                "pool_size": pool_info['pool_size'],
                "max_overflow": pool_info['max_overflow'],
                "pool_timeout": pool_info['pool_timeout'],
                "pool_recycle": pool_info['pool_recycle']
            }
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check including all service components.
    """
    try:
        # Test database
        async with get_db_session() as session:
            db_result = await session.execute(text("SELECT version()"))
            db_version = db_result.scalar()
        
        pool_info = get_connection_info()
        
        return {
            "status": "healthy",
            "timestamp": "2025-01-21T19:15:00Z",  # This would be dynamic in real implementation
            "service": "forge",
            "version": "0.1.0",
            "database": {
                "status": "connected",
                "version": db_version,
                "pool_status": pool_info
            },
            "environment": {
                "workers": pool_info.get('workers', 'unknown'),
                "pool_size": pool_info['pool_size'],
                "max_overflow": pool_info['max_overflow']
            }
        }
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2025-01-21T19:15:00Z"
            }
        ) 