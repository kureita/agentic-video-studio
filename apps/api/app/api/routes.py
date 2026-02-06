from fastapi import APIRouter

from app.api.endpoints import projects, scrape, generate, canvas, brands, trends, strategy, beats, director

router = APIRouter()

router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
router.include_router(generate.router, prefix="/generate", tags=["generate"])
router.include_router(canvas.router, tags=["canvas"])
router.include_router(brands.router, tags=["brands"])
router.include_router(trends.router, tags=["trends"])
router.include_router(strategy.router, tags=["strategy"])
router.include_router(beats.router, tags=["beats"])
router.include_router(director.router, prefix="/director", tags=["director"])
