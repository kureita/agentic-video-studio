from fastapi import APIRouter, Depends

from app.api.endpoints import projects, scrape, generate, canvas, workflow, agent, assets, billing
from app.api.endpoints import public_workflow
from app.api.endpoints import dodo_webhook
from app.core.auth import get_current_user

# ── Public (unauthenticated) router for read-only public access ───────────────
public_router = APIRouter()
public_router.include_router(public_workflow.router, prefix="/public", tags=["public"])
public_router.include_router(dodo_webhook.router, prefix="/billing", tags=["public-billing"])

# ── Internal (unauthenticated) router for Lambda-to-Lambda endpoints ──────────
# These endpoints use their own invoke_secret verification instead of JWT auth.
# This router MUST be included before the authenticated router in main.py
# so that /workflows/execute-background is matched without requiring a Bearer token.
internal_router = APIRouter()

# Import and mount only the internal background endpoint
from app.api.endpoints.workflow import execute_node_background, BackgroundExecuteRequest
from app.api.endpoints.workflow import job_processor_background
internal_router.add_api_route(
    "/workflows/execute-background",
    execute_node_background,
    methods=["POST"],
    tags=["internal"],
)
internal_router.add_api_route(
    "/workflows/job-processor",
    job_processor_background,
    methods=["POST"],
    tags=["internal"],
)

# ── All routes under this router require authentication ───────────────────────
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
