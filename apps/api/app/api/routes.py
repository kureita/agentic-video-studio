from fastapi import APIRouter

from app.api.endpoints import projects, scrape, generate, canvas

router = APIRouter()

router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
router.include_router(generate.router, prefix="/generate", tags=["generate"])
router.include_router(canvas.router, tags=["canvas"])

