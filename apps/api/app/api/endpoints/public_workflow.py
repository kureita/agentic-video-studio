"""Public (unauthenticated) read-only workflow endpoints.

These endpoints allow anyone with a link to view a public workflow
and its S3 assets via presigned URLs — no login required.
"""

from typing import List, Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import get_database
from app.api.endpoints.workflow import (
    serialize_workflow,
    presign_urls,
    WorkflowResponse,
)
from app.core.model_registry import get_models_for_api

router = APIRouter()


@router.get("/models")
async def public_get_models():
    """Public model catalog (no auth). Same data as /billing/models."""
    return {"models": get_models_for_api()}


def get_workflows_collection():
    db = get_database()
    return db["workflows"]


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_public_workflow(workflow_id: str):
    """Get a public workflow by ID. Returns 404 if workflow doesn't exist or is not public."""
    collection = get_workflows_collection()

    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")

    workflow = await collection.find_one({"_id": oid, "is_public": True})

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found or is not public")

    serialized = presign_urls(serialize_workflow(workflow))
    print(f"[PublicWorkflow] Retrieved public workflow {workflow_id}: {len(serialized['nodes'])} nodes")

    return serialized


class PublicPresignRequest(BaseModel):
    urls: List[str]


@router.post("/workflows/presign")
async def public_presign_urls(request: PublicPresignRequest):
    """Generate fresh presigned URLs for S3 assets.

    This is the public equivalent of the authenticated /workflows/presign endpoint.
    It only presigns URLs that look like valid S3 asset URLs (kureita bucket).
    """
    from app.services.storage_service import S3StorageService

    s3_service = S3StorageService()

    result = {}
    for url in request.urls[:50]:  # Cap at 50 URLs per request
        if S3StorageService.is_s3_url(url):
            result[url] = s3_service.get_presigned_url(url)
        else:
            result[url] = url

    return {"urls": result}
