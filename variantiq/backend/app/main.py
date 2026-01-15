"""Main FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.base import close_db, init_db

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        None
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{__version__}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Initialize database (only in development)
    if settings.is_development():
        logger.warning("Initializing database in development mode")
        await init_db()

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application")
    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.APP_DESCRIPTION,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Add Gzip middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount Prometheus metrics endpoint
if settings.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_error"
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "Validation error",
                "type": "validation_error",
                "details": exc.errors()
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error" if settings.is_production() else str(exc),
                "type": "internal_error"
            }
        },
    )


# Health check endpoints
@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "version": __version__,
        "environment": settings.ENVIRONMENT
    }


@app.get("/", tags=["root"])
async def root() -> dict:
    """
    Root endpoint with API information.

    Returns:
        dict: API information
    """
    return {
        "name": settings.APP_NAME,
        "version": __version__,
        "description": settings.APP_DESCRIPTION,
        "docs": "/docs",
        "health": "/health"
    }


# Include API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development(),
        log_level=settings.LOG_LEVEL.lower(),
    )
