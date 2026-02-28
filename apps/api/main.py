from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    await connect_to_mongo()
    
    # Ensure static directories exist
    Path("static/videos").mkdir(parents=True, exist_ok=True)
    Path("static/images").mkdir(parents=True, exist_ok=True)
    Path("static/audio").mkdir(parents=True, exist_ok=True)
    Path("static/uploads").mkdir(parents=True, exist_ok=True)
    
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
    if request.method == "OPTIONS" and request.url.path.startswith("/static"):
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
    if request.url.path.startswith("/static"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

    return response


# Mount static files for serving videos/images/audio
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


# Include API routes
app.include_router(api_router, prefix="/api")
