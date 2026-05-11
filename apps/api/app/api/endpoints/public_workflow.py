"""Public (unauthenticated) read-only workflow endpoints.

These endpoints allow anyone with a link to view a public workflow
and its S3 assets via presigned URLs — no login required.
"""

from typing import List

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.database import get_database
from app.api.endpoints.workflow import (
    serialize_workflow,
    presign_urls,
    WorkflowResponse,
)
from app.core.model_registry import get_models_for_api
from app.services.fal_pricing import FalPricingService

router = APIRouter()


@router.get("/models")
async def public_get_models():
    """Public model catalog (no auth). Same data as /billing/models."""
    pricing = FalPricingService(get_database())
    return {"models": await pricing.enrich_models_for_user_estimates(get_models_for_api())}


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


@router.api_route("/media-proxy", methods=["GET", "HEAD"])
async def media_proxy(url: str, request: Request):
    """Redirect to a freshly-presigned S3 URL for the given Kureita asset.

    Used by the browser-side Remotion renderer so each render fetches a brand
    new URL (cache-busting any stale opaque <video>-tag responses) and so the
    redirect target is always a valid signature even if the original stored URL
    is stale. The redirect target itself is the actual S3 object, which serves
    the bucket's CORS headers — so this remains a tiny Lambda response (no
    streaming through API Gateway).

    Both GET and HEAD are supported because Mediabunny may probe object size
    with a HEAD before a range GET. We presign for whichever method the client
    used so S3 doesn't reject HEAD against a GET-only signature.
    """
    from urllib.parse import urlparse

    from app.services.storage_service import S3StorageService

    if not S3StorageService.is_s3_url(url):
        raise HTTPException(status_code=400, detail="Only Kureita S3 media URLs can be proxied")

    s3_service = S3StorageService()
    raw_url = S3StorageService.strip_presigned_params(url)
    key = urlparse(raw_url).path.lstrip("/")
    if not key:
        raise HTTPException(status_code=400, detail="Invalid S3 asset URL")

    method = "head_object" if request.method == "HEAD" else "get_object"
    try:
        presigned = s3_service.s3_client.generate_presigned_url(
            ClientMethod=method,
            Params={"Bucket": s3_service.bucket, "Key": key},
            ExpiresIn=3600,
        )
    except Exception as err:
        print(f"[PublicWorkflow] media-proxy presign failed for {key}: {err}")
        raise HTTPException(status_code=500, detail="Could not presign media URL")

    response = RedirectResponse(url=presigned, status_code=307)
    response.headers["Cache-Control"] = "no-store"
    return response
