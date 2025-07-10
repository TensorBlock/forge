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


# Get environment
is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

app = FastAPI(
    title="Forge API",
    description="A middleware service for managing AI model provider API keys",
    version="0.1.0",
    docs_url="/docs" if not is_production else None,
    redoc_url="/redoc" if not is_production else None,
    openapi_url="/openapi.json" if not is_production else None,
)

### Exception handlers block ###

# Add exception handler for ProviderAuthenticationException
@app.exception_handler(ProviderAuthenticationException)
async def provider_authentication_exception_handler(request: Request, exc: ProviderAuthenticationException):
    return HTTPException(
        status_code=401,
        detail=f"Authentication failed for provider {exc.provider_name}"
    )

# Add exception handler for InvalidProviderException
@app.exception_handler(InvalidProviderException)
async def invalid_provider_exception_handler(request: Request, exc: InvalidProviderException):
    return HTTPException(
        status_code=400,
        detail=f"{str(exc)}. Please verify your provider and model details by calling the /models endpoint or visiting https://tensorblock.co/api-docs/model-ids, and ensure you're using a valid provider name, model name, and model ID."
    )

# Add exception handler for BaseInvalidProviderSetupException
@app.exception_handler(BaseInvalidProviderSetupException)
async def base_invalid_provider_setup_exception_handler(request: Request, exc: BaseInvalidProviderSetupException):
    return HTTPException(
        status_code=400,
        detail=str(exc)
    )

# Add exception handler for ProviderAPIException
@app.exception_handler(ProviderAPIException)
async def provider_api_exception_handler(request: Request, exc: ProviderAPIException):
    return HTTPException(
        status_code=exc.error_code,
        detail=f"Provider API error: {exc.provider_name} {exc.error_code} {exc.error_message}"
    )

# Add exception handler for BaseInvalidRequestException
@app.exception_handler(BaseInvalidRequestException)
async def base_invalid_request_exception_handler(request: Request, exc: BaseInvalidRequestException):
    return HTTPException(
        status_code=400,
        detail=str(exc)
    )

# Add exception handler for BaseInvalidForgeKeyException
@app.exception_handler(BaseInvalidForgeKeyException)
async def base_invalid_forge_key_exception_handler(request: Request, exc: BaseInvalidForgeKeyException):
    return HTTPException(
        status_code=401,
        detail=f"Invalid Forge key: {exc.error}"
    )

# Add exception handler for NotImplementedError
@app.exception_handler(NotImplementedError)
async def not_implemented_error_handler(request: Request, exc: NotImplementedError):
    return HTTPException(
        status_code=404,
        detail=f"Not implemented: {exc}"
    )
### Exception handlers block ends ###


# Middleware to log slow requests
@app.middleware("http")
async def log_latency(request: Request, call_next):
    start_time = (
        time.time()
    )  # Renamed from start to avoid conflict with existing start_time
    try:
        response = await call_next(request)
        return response
    finally:
        duration = time.time() - start_time
        if duration > SLOW_REQUEST_THRESHOLD_SECONDS:  # More than the defined threshold
            logger.warning(
                f"[SLOW] {request.method} {request.url.path} took {duration:.2f}s"
            )


# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify the actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers under v1 prefix
v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(users.router, prefix="/users", tags=["Users"])
v1_router.include_router(
    provider_keys.router, prefix="/provider-keys", tags=["Provider Keys"]
)
v1_router.include_router(stats.router, prefix="/stats", tags=["Usage Statistics"])
v1_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
v1_router.include_router(api_auth.router, prefix="/api", tags=["Unified API"])
v1_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])

# OpenAI-compatible API endpoints
v1_router.include_router(proxy.router, tags=["OpenAI API"])

# Include v1 router in main app
app.include_router(v1_router)


@app.get("/")
def read_root():
    response = {
        "name": "Forge API",
        "version": "0.1.0",
        "description": "A middleware service for managing AI model provider API keys",
    }
    if not is_production:
        response["documentation"] = "/docs"
    return response


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "False").lower() == "true"

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=debug)
