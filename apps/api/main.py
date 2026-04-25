from contextlib import asynccontextmanager
from pathlib import Path
import logging
import re
import tempfile
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from pymongo.errors import PyMongoError

# Configure root logging so Python `logging.getLogger(__name__)` calls
# (used across FalService, FalPricingService, fal webhook, verifier, etc.)
# are captured by CloudWatch at INFO level or higher. Override via LOG_LEVEL.
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    force=True,
)
# Tame chatty third-party libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection, is_database_healthy


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    connected = await connect_to_mongo()
    if not connected:
        print("⚠ Continuing startup without MongoDB. API routes that need DB may return 503.")
    
    # Ensure static directories exist
    Path("static/videos").mkdir(parents=True, exist_ok=True)
    Path("static/images").mkdir(parents=True, exist_ok=True)
    Path("static/audio").mkdir(parents=True, exist_ok=True)
    
    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(
    title="Kureita API",
    description="AI-powered video production platform",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS middleware for API routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cors_static_files(request: Request, call_next):
    """Add CORS headers to static file responses.
    
    FastAPI's CORSMiddleware can be unreliable with mounted StaticFiles
    sub-applications. This middleware explicitly handles CORS for /static paths.
    """
    # Handle preflight OPTIONS requests for static files
    if request.method == "OPTIONS" and (request.url.path.startswith("/static") or request.url.path.startswith("/tmp_uploads")):
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400",
            },
        )

    response = await call_next(request)

    # Inject CORS headers into static file responses
    if request.url.path.startswith("/static") or request.url.path.startswith("/tmp_uploads"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

    return response


# Ensure static and temp directories exist before mounting
Path("static").mkdir(parents=True, exist_ok=True)
tmp_uploads_path = "/tmp/kureita_uploads"
os.makedirs(tmp_uploads_path, exist_ok=True)

# Mount static files for serving videos/images/audio
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/tmp_uploads", StaticFiles(directory=tmp_uploads_path), name="tmp_uploads")


@app.get("/health")
async def health_check():
    db_ok = await is_database_healthy()
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "0.1.0",
        "dependencies": {
            "mongodb": "up" if db_ok else "down",
        },
    }


def _cors_headers_for(request: Request) -> dict:
    """CORS headers for error responses.

    Starlette's CORSMiddleware does not run on responses built by exception
    handlers, so error responses arrive at the browser without
    Access-Control-Allow-Origin and surface as opaque CORS failures. Mirror the
    allowlist/regex used by CORSMiddleware so 4xx/5xx responses carry the same
    headers as successful ones.
    """
    origin = request.headers.get("origin")
    if not origin:
        return {}

    allowed = origin in settings.cors_origins_list or (
        settings.cors_origin_regex
        and re.fullmatch(settings.cors_origin_regex, origin) is not None
    )
    if not allowed:
        return {}

    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


@app.exception_handler(PyMongoError)
async def mongo_error_handler(request: Request, _: PyMongoError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable"},
        headers=_cors_headers_for(request),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Without this, Starlette's ServerErrorMiddleware returns a bare 500
    # that bypasses CORSMiddleware, so the browser surfaces it as a CORS
    # failure instead of the underlying error. Mirror the CORS headers so
    # the actual status reaches the client.
    logging.getLogger(__name__).exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=_cors_headers_for(request),
    )


# Include API routes (order matters: public & internal before authenticated)
from app.api.routes import internal_router, public_router
app.include_router(public_router, prefix="/api")
app.include_router(internal_router, prefix="/api")
app.include_router(api_router, prefix="/api")
