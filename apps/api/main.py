from contextlib import asynccontextmanager
from pathlib import Path
import tempfile
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from pymongo.errors import PyMongoError

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


@app.exception_handler(PyMongoError)
async def mongo_error_handler(_: Request, __: PyMongoError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable"},
    )


# Include API routes (order matters: public & internal before authenticated)
from app.api.routes import internal_router, public_router
app.include_router(public_router, prefix="/api")
app.include_router(internal_router, prefix="/api")
app.include_router(api_router, prefix="/api")
