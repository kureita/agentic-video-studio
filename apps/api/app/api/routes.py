from fastapi import APIRouter, Depends

from app.api.endpoints import projects, scrape, generate, canvas, workflow, agent, assets, billing
from app.core.auth import get_current_user

# All routes under this router require authentication
router = APIRouter(dependencies=[Depends(get_current_user)])

router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
router.include_router(generate.router, prefix="/generate", tags=["generate"])
router.include_router(canvas.router, tags=["canvas"])
router.include_router(workflow.router, prefix="/workflows", tags=["workflows"])
router.include_router(agent.router, prefix="/agent", tags=["agent"])
router.include_router(assets.router, prefix="/assets", tags=["assets"])
router.include_router(billing.router, tags=["billing"])


# ============================================
# Auth Endpoints
# ============================================

@router.get("/me", tags=["auth"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return {
        "id": current_user.get("_id"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "created_at": current_user.get("created_at", "").isoformat()
            if hasattr(current_user.get("created_at", ""), "isoformat")
            else str(current_user.get("created_at", "")),
    }
