from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for serving videos
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


# Include API routes
app.include_router(api_router, prefix="/api")
