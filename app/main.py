"""
Main FastAPI application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError

from app.api.v1 import api_router
from app.core.config import settings
from app.db.base import engine
from app.models import Base
import logging

# Configure logging BEFORE creating the app
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:\t%(name)s\t%(message)s',
    handlers=[
        logging.StreamHandler()  # Output to console
    ]
)
logging.getLogger("uvicorn").setLevel(logging.INFO)

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Intelligent Learning Assistant with Interaction and Knowledge Testing",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS - Always apply middleware
cors_origins = settings.BACKEND_CORS_ORIGINS if settings.BACKEND_CORS_ORIGINS else ["*"]
print(f"🔧 CORS enabled for origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors.

    Args:
        request: Request object
        exc: Validation exception

    Returns:
        JSON response with error details
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handle all unhandled exceptions.

    Args:
        request: Request object
        exc: Exception

    Returns:
        JSON response with error message
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "message": str(exc)},
    )


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """
    Run on application startup.
    """
    print(f"🚀 Starting {settings.PROJECT_NAME}")
    print(f"📚 Documentation available at: http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Run on application shutdown.
    """
    print(f"👋 Shutting down {settings.PROJECT_NAME}")


# Health check endpoint
@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint - Health check.

    Returns:
        Status message
    """
    return {
        "message": "Intelligent Learning Assistant API",
        "status": "healthy",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy"}


# Include API routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
