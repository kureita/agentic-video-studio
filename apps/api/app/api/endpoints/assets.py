import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form, Query
from pydantic import BaseModel
from app.services.storage_service import StorageService
from app.core.dependencies import get_storage_service
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_database
from app.api.endpoints.user_assets import register_asset

router = APIRouter()

BYTES_PER_MB = 1024 * 1024
MEDIA_EXT_TO_KIND = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".gif": "image",
    ".bmp": "image",
    ".svg": "image",
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
    ".avi": "video",
    ".mkv": "video",
    ".mp3": "audio",
    ".wav": "audio",
    ".ogg": "audio",
    ".flac": "audio",
    ".aac": "audio",
    ".m4a": "audio",
}


def _bytes_from_mb(value: int) -> int:
    return int(value) * BYTES_PER_MB


def _tenant_quota_bytes() -> int:
    return _bytes_from_mb(settings.tenant_asset_storage_quota_mb)


def _infer_media_kind(content_type: Optional[str], filename: Optional[str]) -> str:
    content_type = (content_type or "").split(";")[0].strip().lower()
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("audio/"):
        return "audio"

    ext = os.path.splitext(filename or "")[1].lower()
    return MEDIA_EXT_TO_KIND.get(ext, "unknown")


def _max_file_size_for_kind(kind: str) -> int:
    if kind == "image":
        return _bytes_from_mb(settings.upload_max_image_mb)
    if kind == "video":
        return _bytes_from_mb(settings.upload_max_video_mb)
    if kind == "audio":
        return _bytes_from_mb(settings.upload_max_audio_mb)
    raise HTTPException(status_code=400, detail="Unsupported media type")


def _validate_file_size(kind: str, file_size: int, *, api_upload: bool = False) -> int:
    if file_size <= 0:
        raise HTTPException(status_code=400, detail="File size is required")

    max_file_size = _max_file_size_for_kind(kind)
    if api_upload:
        max_file_size = min(max_file_size, _bytes_from_mb(settings.upload_api_max_mb))

    if file_size > max_file_size:
        raise HTTPException(
            status_code=413,
            detail={
                "message": f"{kind.capitalize()} file is too large",
                "max_file_size": max_file_size,
                "max_file_size_mb": round(max_file_size / BYTES_PER_MB, 2),
            },
        )
    return max_file_size


async def _used_storage_bytes(user_id: str) -> int:
    db = get_database()
    result = await db["user_assets"].aggregate([
        {"$match": {"user_id": user_id, "_sentinel": {"$ne": True}}},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$asset_size_bytes", 0]}}}},
    ]).to_list(length=1)
    return int(result[0]["total"]) if result else 0


async def _ensure_storage_quota(user_id: str, incoming_size: int) -> int:
    used = await _used_storage_bytes(user_id)
    quota = _tenant_quota_bytes()
    if used + incoming_size > quota:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "Tenant upload storage quota exceeded",
                "used_bytes": used,
                "incoming_bytes": incoming_size,
                "quota_bytes": quota,
                "quota_mb": settings.tenant_asset_storage_quota_mb,
            },
        )
    return used


def _s3_key_from_url(file_url: str) -> str:
    clean_url = file_url.split("?", 1)[0]
    path = urlparse(clean_url).path
    if path.startswith("/"):
        path = path[1:]
    if not path:
        raise HTTPException(status_code=400, detail="Invalid uploaded file URL")
    return path

@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    workflow_id: Optional[str] = Form(default=None),
    workflow_name: Optional[str] = Form(default=None),
    current_user: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service)
) -> Dict[str, Any]:
    """
    Upload an asset file (image/video/audio).
    Returns the URL to the uploaded file.
    """
    try:
        user_id = current_user.get("_id", "")
        media_kind = _infer_media_kind(file.content_type, file.filename)
        file_bytes = await file.read()
        file_size = len(file_bytes)
        _validate_file_size(media_kind, file_size, api_upload=True)
        await _ensure_storage_quota(user_id, file_size)

        # Generate unique filename to prevent collisions
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Upload using storage service
        file_url = await storage.upload_file(file_bytes, unique_filename, file.content_type)

        try:
            await register_asset(
                user_id=user_id,
                workflow_id=workflow_id or "unknown",
                workflow_name=workflow_name or "Untitled Workflow",
                node_id=f"chat-upload-{uuid.uuid4()}",
                node_type="mediaUpload",
                asset_url=file_url,
                node_data={
                    "mediaType": media_kind,
                    "fileSizeBytes": file_size,
                    "mimeType": file.content_type,
                    "filename": file.filename,
                },
                asset_size_bytes=file_size,
                mime_type=file.content_type,
                filename=file.filename,
            )
        except Exception as reg_err:
            print(f"[Assets] Asset registration skipped: {reg_err}")
        
        return {
            "success": True,
            "filename": file.filename,
            "url": file_url,
            "type": file.content_type,
            "asset_size_bytes": file_size,
        }
    except HTTPException:
        raise
        
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/upload/presigned")
async def get_presigned_upload_url(
    filename: str,
    content_type: str,
    file_size: int = Query(..., ge=1),
    current_user: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service)
) -> Dict[str, Any]:
    """
    Generate a presigned URL for direct upload to S3.
    Use this for large files to bypass Lambda payload limits.
    """
    try:
        user_id = current_user.get("_id", "")
        media_kind = _infer_media_kind(content_type, filename)
        max_file_size = _validate_file_size(media_kind, file_size)
        used_bytes = await _ensure_storage_quota(user_id, file_size)

        # Generate unique filename
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        presigned_data = storage.generate_presigned_upload_url(
            unique_filename,
            content_type,
            max_file_size=max_file_size,
        )

        key = presigned_data.get("key")
        if key:
            db = get_database()
            await db["pending_uploads"].update_one(
                {"user_id": user_id, "key": key},
                {
                    "$set": {
                        "user_id": user_id,
                        "key": key,
                        "file_url": presigned_data.get("file_url"),
                        "filename": filename,
                        "content_type": content_type,
                        "media_kind": media_kind,
                        "declared_size_bytes": int(file_size),
                        "max_file_size": int(max_file_size),
                        "status": "pending",
                        "created_at": datetime.now(timezone.utc),
                        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                    }
                },
                upsert=True,
            )
        
        return {
            "success": True,
            "media_kind": media_kind,
            "max_file_size": max_file_size,
            "tenant_used_bytes": used_bytes,
            "tenant_quota_bytes": _tenant_quota_bytes(),
            **presigned_data # Returns upload_url, file_url, key (or is_local: True)
        }
    except HTTPException:
        raise
    except NotImplementedError:
        # Fallback for local storage which might not support presigned URLs
        return {"success": False, "is_local": True}
    except Exception as e:
        print(f"Presigned upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")


class ConfirmPresignedUploadRequest(BaseModel):
    file_url: str
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    node_id: Optional[str] = None
    node_type: str = "mediaUpload"
    node_data: Optional[Dict[str, Any]] = None


@router.post("/upload/presigned/confirm")
async def confirm_presigned_upload(
    request: ConfirmPresignedUploadRequest,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Confirm a direct S3 upload, enforce actual-size quota, and register it."""
    from app.services.storage_service import S3StorageService

    user_id = current_user.get("_id", "")
    key = _s3_key_from_url(request.file_url)
    db = get_database()
    pending_col = db["pending_uploads"]
    pending = await pending_col.find_one({"user_id": user_id, "key": key, "status": "pending"})
    if not pending:
        raise HTTPException(status_code=404, detail="Pending upload not found or expired")

    s3 = S3StorageService()
    try:
        head = s3.s3_client.head_object(Bucket=s3.bucket, Key=key)
    except Exception as err:
        raise HTTPException(status_code=404, detail=f"Uploaded object not found: {err}") from err

    actual_size = int(head.get("ContentLength") or 0)
    content_type = str(head.get("ContentType") or pending.get("content_type") or "")
    filename = str(pending.get("filename") or os.path.basename(key))
    media_kind = _infer_media_kind(content_type, filename)
    _validate_file_size(media_kind, actual_size)

    clean_url = S3StorageService.strip_presigned_params(request.file_url)
    existing = await db["user_assets"].find_one({"user_id": user_id, "url": clean_url})
    if not existing:
        try:
            used_bytes = await _ensure_storage_quota(user_id, actual_size)
        except HTTPException:
            await s3.delete_file(clean_url)
            await pending_col.update_one(
                {"_id": pending["_id"]},
                {"$set": {"status": "rejected", "rejected_at": datetime.now(timezone.utc)}},
            )
            raise
    else:
        used_bytes = await _used_storage_bytes(user_id)

    node_data = {
        **(request.node_data or {}),
        "mediaType": media_kind,
        "fileSizeBytes": actual_size,
        "mimeType": content_type,
        "filename": filename,
    }
    await register_asset(
        user_id=user_id,
        workflow_id=request.workflow_id or "unknown",
        workflow_name=request.workflow_name or "Untitled Workflow",
        node_id=request.node_id or f"upload-{uuid.uuid4()}",
        node_type=request.node_type or "mediaUpload",
        asset_url=clean_url,
        node_data=node_data,
        asset_size_bytes=actual_size,
        mime_type=content_type,
        filename=filename,
    )
    await pending_col.update_one(
        {"_id": pending["_id"]},
        {
            "$set": {
                "status": "confirmed",
                "confirmed_at": datetime.now(timezone.utc),
                "actual_size_bytes": actual_size,
            }
        },
    )

    return {
        "success": True,
        "url": clean_url,
        "type": content_type,
        "media_kind": media_kind,
        "asset_size_bytes": actual_size,
        "tenant_used_bytes": used_bytes + (0 if existing else actual_size),
        "tenant_quota_bytes": _tenant_quota_bytes(),
    }
