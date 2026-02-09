from fastapi import APIRouter

from app.api.endpoints import projects, scrape, generate, canvas, workflow, agent, assets

router = APIRouter()

router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
router.include_router(generate.router, prefix="/generate", tags=["generate"])
router.include_router(canvas.router, tags=["canvas"])
router.include_router(workflow.router, prefix="/workflows", tags=["workflows"])
router.include_router(agent.router, prefix="/agent", tags=["agent"])
router.include_router(assets.router, prefix="/assets", tags=["assets"])

