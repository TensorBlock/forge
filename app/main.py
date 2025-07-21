import os
import time
from collections.abc import Callable

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import (
    api_auth,
    api_keys,
    auth,
    health,
    provider_keys,
    proxy,
    stats,
    users,
    webhooks,
)
from app.core.database import engine
from app.core.logger import get_logger
from app.models.base import Base
from app.exceptions.exceptions import ProviderAuthenticationException, InvalidProviderException, BaseInvalidProviderSetupException, \
    ProviderAPIException, BaseInvalidRequestException, BaseInvalidForgeKeyException

load_dotenv()

# Configure logging
logger = get_logger(name="forge")

# Threshold for slow request logging (in seconds)
SLOW_REQUEST_THRESHOLD_SECONDS = 10

# Create database tables
Base.metadata.create_all(bind=engine)

# Create v1 router
v1_router = APIRouter(prefix="/v1")


# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()

        # Get request details
        method = request.method
        url = request.url.path
        query_params = str(request.query_params) if request.query_params else ""
        client = request.client.host if request.client else "unknown"

        # Log request received
        logger.info(f"Request received: {method} {url}{query_params} from {client}")

        # Process the request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Log response details
        logger.info(
            f"Request completed: {method} {url} - Status: {response.status_code} - "
            f"Took: {process_time:.4f}s"
        )

        return response


# Exception handlers
class ForgeExceptionHandler:
    """Custom exception handlers for Forge-specific errors."""

    @staticmethod
    async def handle_provider_auth_exception(request: Request, exc: ProviderAuthenticationException):
        logger.warning(f"Provider authentication failed: {exc.detail}")
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers or {}
        )

    @staticmethod
    async def handle_invalid_provider_exception(request: Request, exc: InvalidProviderException):
        logger.warning(f"Invalid provider: {exc.detail}")
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers or {}
        )

    @staticmethod
    async def handle_base_invalid_provider_setup_exception(request: Request, exc: BaseInvalidProviderSetupException):
        logger.warning(f"Invalid provider setup: {exc.detail}")
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers or {}
        )

    @staticmethod
    async def handle_provider_api_exception(request: Request, exc: ProviderAPIException):
        logger.error(f"Provider API error: {exc.detail}")
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers or {}
        )

    @staticmethod
    async def handle_base_invalid_request_exception(request: Request, exc: BaseInvalidRequestException):
        logger.warning(f"Invalid request: {exc.detail}")
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers or {}
        )

    @staticmethod
    async def handle_base_invalid_forge_key_exception(request: Request, exc: BaseInvalidForgeKeyException):
        logger.warning(f"Invalid Forge key: {exc.detail}")
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers or {}
        )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Forge API",
        description="Unified AI model provider API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Add exception handlers
    app.add_exception_handler(ProviderAuthenticationException, ForgeExceptionHandler.handle_provider_auth_exception)
    app.add_exception_handler(InvalidProviderException, ForgeExceptionHandler.handle_invalid_provider_exception)
    app.add_exception_handler(BaseInvalidProviderSetupException, ForgeExceptionHandler.handle_base_invalid_provider_setup_exception)
    app.add_exception_handler(ProviderAPIException, ForgeExceptionHandler.handle_provider_api_exception)
    app.add_exception_handler(BaseInvalidRequestException, ForgeExceptionHandler.handle_base_invalid_request_exception)
    app.add_exception_handler(BaseInvalidForgeKeyException, ForgeExceptionHandler.handle_base_invalid_forge_key_exception)

    # Include routers
    v1_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
    v1_router.include_router(api_auth.router, prefix="/api-auth", tags=["api-authentication"])
    v1_router.include_router(users.router, prefix="/users", tags=["users"])
    v1_router.include_router(provider_keys.router, prefix="/provider-keys", tags=["provider-keys"])
    v1_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
    v1_router.include_router(proxy.router, tags=["proxy"])
    v1_router.include_router(stats.router, prefix="/stats", tags=["stats"])
    v1_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

    # Health check routes (not versioned)
    app.include_router(health.router, tags=["health"])
    
    # Include v1 router
    app.include_router(v1_router)

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "Welcome to Forge API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health"
        }

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "False").lower() == "true"

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=debug)
