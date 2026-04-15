"""User Assets Endpoint — persistent asset registry backed by MongoDB.

Assets are recorded in the `user_assets` collection when they are generated or
uploaded.  On the first call we backfill from existing workflow outputs so
nothing is lost.  Deletion removes from both the collection AND S3.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import re

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.database import get_database

router = APIRouter()


# ── Response Models ──────────────────────────────────────────────────

class AssetItem(BaseModel):
    """A single asset (image, video, audio)."""
    node_id: str
    node_type: str          # imageGen, videoGen, audioGen, mediaUpload, editorAgent
    asset_category: str     # "generated_image", "generated_video", "generated_audio", "uploaded", "rendered_video"
    url: str                # Raw S3 URL
    presigned_url: str      # Presigned URL for display
    node_data: Optional[Dict[str, Any]] = None  # Original node settings (prompt, model, ratio, etc.)


class WorkflowAssets(BaseModel):
    """All assets belonging to a single workflow."""
    workflow_id: str
    workflow_name: str
    updated_at: str
    assets: List[AssetItem] = []


class UserAssetsResponse(BaseModel):
    """Top-level response wrapping all workflows."""
    workspaces: List[WorkflowAssets] = []
    total_assets: int = 0


# ── Category mapping ─────────────────────────────────────────────────

NODE_TYPE_TO_CATEGORY = {
    "imageGen":     "generated_image",
    "videoGen":     "generated_video",
    "audioGen":     "generated_audio",
    "mediaUpload":  "uploaded",
    "editorAgent":  "rendered_video",
}

# File extensions we consider valid media assets
MEDIA_EXTENSIONS = re.compile(
    r'\.(jpg|jpeg|png|webp|gif|bmp|svg'      # images
    r'|mp4|mov|webm|avi|mkv'                   # video
    r'|mp3|wav|ogg|flac|aac|m4a'               # audio
    r')(\?|$)',                                 # end or querystring
    re.IGNORECASE,
)


def _is_media_url(value: Any) -> bool:
    """Check if a value is a valid media asset URL (image/video/audio file)."""
    if not isinstance(value, str):
        return False
    if not value.startswith("http"):
        return False
    if MEDIA_EXTENSIONS.search(value):
        return True
    if "kureita" in value and "amazonaws.com" in value:
        return True
    return False


def _ensure_utc_isoformat(dt: Any) -> str:
    if not isinstance(dt, datetime):
        return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ── Registration helper (call from workflow execution) ────────────────

async def register_asset(
    user_id: str,
    workflow_id: str,
    workflow_name: str,
    node_id: str,
    node_type: str,
    asset_url: str,
    node_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Register a newly created/uploaded asset in the user_assets collection.

    Idempotent — if the URL already exists for this user it is not duplicated.
    """
    db = get_database()
    if db is None:
        return

    collection = db["user_assets"]
    category = NODE_TYPE_TO_CATEGORY.get(node_type, "uploaded")

    # Strip any presigned params to get the canonical S3 URL
    from app.services.storage_service import S3StorageService
    clean_url = S3StorageService.strip_presigned_params(asset_url)

    existing = await collection.find_one({"user_id": user_id, "url": clean_url})
    if existing:
        return  # already registered

    # Only keep relevant settings from node_data (prompt, model, ratio, etc.)
    safe_node_data = None
    if node_data and isinstance(node_data, dict):
        # Keep only serializable settings, drop transient runtime fields
        keep_keys = {"prompt", "instruction", "text", "model", "ratio", "count", "duration", "resolution",
                     "voice", "audioType", "mediaType", "generateAudio"}
        safe_node_data = {k: v for k, v in node_data.items() if k in keep_keys and v is not None}

    doc = {
        "user_id": user_id,
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "node_id": node_id,
        "node_type": node_type,
        "asset_category": category,
        "url": clean_url,
        "node_data": safe_node_data,
        "created_at": datetime.now(timezone.utc),
    }
    await collection.insert_one(doc)
    print(f"[UserAssets] Registered asset: {category} in '{workflow_name}' → {clean_url[:80]}...")


async def _backfill_from_workflows(user_id: str) -> None:
    """
    One-time migration: scan all of the user's workflows and register every
    media output that isn't already tracked.
    """
    db = get_database()
    if db is None:
        return

    assets_col = db["user_assets"]
    workflows_col = db["workflows"]

    # Check if we've already backfilled for this user
    count = await assets_col.count_documents({"user_id": user_id})
    if count > 0:
        return  # already has records — skip expensive scan

    query = {"$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]}
    projection = {"_id": 1, "name": 1, "nodes": 1, "outputs": 1, "user_id": 1, "updated_at": 1}
    cursor = workflows_col.find(query, projection).sort("updated_at", -1)
    workflows = await cursor.to_list(length=200)

    docs_to_insert: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for w in workflows:
        wf_id = str(w["_id"])
        wf_name = w.get("name", "Untitled Workflow")
        outputs: Dict[str, Any] = w.get("outputs", {})
        nodes_list: List[Dict] = w.get("nodes", [])

        # Build node_id → type map
        node_type_map: Dict[str, str] = {}
        for n in nodes_list:
            nid = n.get("id")
            ntype = n.get("type")
            if nid and ntype:
                node_type_map[nid] = ntype

        for key, value in outputs.items():
            if "__" in key:
                continue
            if not _is_media_url(value):
                continue

            node_type = node_type_map.get(key)
            if node_type is None:
                continue
            category = NODE_TYPE_TO_CATEGORY.get(node_type)
            if category is None:
                continue

            from app.services.storage_service import S3StorageService
            clean_url = S3StorageService.strip_presigned_params(value)
            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            # Also save historical node settings to the asset
            node_data = None
            for n in nodes_list:
                if n.get("id") == key:
                    data = n.get("data", {})
                    keep_keys = {"prompt", "instruction", "text", "model", "ratio", "count", "duration", "resolution", "voice", "audioType", "mediaType", "generateAudio"}
                    node_data = {k: v for k, v in data.items() if k in keep_keys and v is not None}
                    break

            docs_to_insert.append({
                "user_id": user_id,
                "workflow_id": wf_id,
                "workflow_name": wf_name,
                "node_id": key,
                "node_type": node_type,
                "asset_category": category,
                "url": clean_url,
                "node_data": node_data,
                "created_at": w.get("updated_at", datetime.now(timezone.utc)),
            })

    if docs_to_insert:
        await assets_col.insert_many(docs_to_insert)
        print(f"[UserAssets] Backfilled {len(docs_to_insert)} assets for user {user_id}")
    else:
        # Insert a sentinel so we don't re-scan next time
        await assets_col.insert_one({
            "user_id": user_id,
            "_sentinel": True,
            "created_at": datetime.now(timezone.utc),
        })
        print(f"[UserAssets] No assets found to backfill for user {user_id}")


# ── GET — list assets ─────────────────────────────────────────────────

@router.get("", response_model=UserAssetsResponse)
async def list_user_assets(
    current_workflow_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    List all persistent assets for the authenticated user, grouped by workflow.

    On first call, backfills from existing workflow outputs.
    """
    db = get_database()
    assets_col = db["user_assets"]
    user_id = current_user.get("_id")

    # Backfill from workflows if this is the user's first time
    await _backfill_from_workflows(user_id)

    # Fetch all registered assets for this user (exclude sentinels)
    cursor = assets_col.find(
        {"user_id": user_id, "_sentinel": {"$ne": True}},
    ).sort("created_at", -1)
    all_assets = await cursor.to_list(length=2000)

    from app.services.storage_service import S3StorageService
    s3 = S3StorageService()

    # Group by workflow
    from collections import OrderedDict
    workflow_groups: Dict[str, Dict[str, Any]] = OrderedDict()

    for doc in all_assets:
        wf_id = doc.get("workflow_id", "unknown")
        wf_name = doc.get("workflow_name", "Untitled Workflow")
        url = doc.get("url", "")

        if wf_id not in workflow_groups:
            workflow_groups[wf_id] = {
                "workflow_id": wf_id,
                "workflow_name": wf_name,
                "updated_at": _ensure_utc_isoformat(doc.get("created_at")),
                "assets": [],
            }

        try:
            if S3StorageService.is_s3_url(url):
                presigned = s3.get_presigned_url(url)
            else:
                presigned = url
        except Exception:
            presigned = url

        workflow_groups[wf_id]["assets"].append(AssetItem(
            node_id=doc.get("node_id", ""),
            node_type=doc.get("node_type", "mediaUpload"),
            asset_category=doc.get("asset_category", "uploaded"),
            url=url,
            presigned_url=presigned,
            node_data=doc.get("node_data"),
        ))

    result_workspaces = [
        WorkflowAssets(**data)
        for data in workflow_groups.values()
        if data["assets"]
    ]

    # Move current workflow to top if specified
    if current_workflow_id:
        for i, ws in enumerate(result_workspaces):
            if ws.workflow_id == current_workflow_id:
                result_workspaces.insert(0, result_workspaces.pop(i))
                break

    total = sum(len(ws.assets) for ws in result_workspaces)
    return UserAssetsResponse(workspaces=result_workspaces, total_assets=total)


# ── DELETE — permanently remove an asset ──────────────────────────────

class DeleteAssetRequest(BaseModel):
    url: str


@router.delete("", response_model=dict)
async def delete_user_asset(
    req: DeleteAssetRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Permanently delete an asset from S3 and the registry.
    """
    db = get_database()
    assets_col = db["user_assets"]
    user_id = current_user.get("_id")

    from app.services.storage_service import S3StorageService
    s3 = S3StorageService()

    clean_url = S3StorageService.strip_presigned_params(req.url)

    # Verify ownership — only delete if it belongs to this user
    doc = await assets_col.find_one({"user_id": user_id, "url": clean_url})
    if not doc:
        raise HTTPException(status_code=404, detail="Asset not found or not owned by you")

    # Delete from S3
    s3_ok = await s3.delete_file(clean_url)
    if not s3_ok:
        print(f"[UserAssets] Warning: S3 delete failed for {clean_url}, removing from registry anyway")

    # Delete from registry
    await assets_col.delete_many({"user_id": user_id, "url": clean_url})

    return {"success": True}
