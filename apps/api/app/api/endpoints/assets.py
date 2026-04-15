import os
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.services.storage_service import StorageService
from app.core.dependencies import get_storage_service
from app.core.auth import decode_token
from app.core.user import get_or_create_user
from app.api.endpoints.user_assets import register_asset

router = APIRouter()
optional_auth = HTTPBearer(auto_error=False)


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_auth),
) -> Optional[dict]:
    if not credentials:
        return None

    try:
        token_payload = decode_token(credentials.credentials)
        return await get_or_create_user(
            auth0_sub=token_payload.get("sub", ""),
            email=token_payload.get("email", ""),
            name=token_payload.get("name", ""),
        )
    except Exception:
        return None

@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    workflow_id: Optional[str] = Form(default=None),
    workflow_name: Optional[str] = Form(default=None),
    current_user: Optional[dict] = Depends(get_optional_current_user),
    storage: StorageService = Depends(get_storage_service)
) -> Dict[str, Any]:
    """
    Upload an asset file (image/video/audio).
    Returns the URL to the uploaded file.
    """
    try:
        # Generate unique filename to prevent collisions
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Upload using storage service
        file_url = await storage.upload_file(file, unique_filename, file.content_type)

        # Optional registration for "Your Stuff" when upload originates from an authenticated workflow context.
        if current_user and workflow_id:
            try:
                media_type = (file.content_type or "").split("/")[0]
                await register_asset(
                    user_id=current_user.get("_id", ""),
                    workflow_id=workflow_id,
                    workflow_name=workflow_name or "Untitled Workflow",
                    node_id=f"chat-upload-{uuid.uuid4()}",
                    node_type="mediaUpload",
                    asset_url=file_url,
                    node_data={"mediaType": media_type},
                )
            except Exception as reg_err:
                print(f"[Assets] Asset registration skipped: {reg_err}")
        
        return {
            "success": True,
            "filename": file.filename,
            "url": file_url,
            "type": file.content_type
        }
        
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/upload/presigned")
async def get_presigned_upload_url(
    filename: str,
    content_type: str,
    storage: StorageService = Depends(get_storage_service)
) -> Dict[str, Any]:
    """
    Generate a presigned URL for direct upload to S3.
    Use this for large files to bypass Lambda payload limits.
    """
    try:
        # Generate unique filename
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        presigned_data = storage.generate_presigned_upload_url(unique_filename, content_type)
        
        return {
            "success": True,
            **presigned_data # Returns upload_url, file_url, key (or is_local: True)
        }
    except NotImplementedError:
        # Fallback for local storage which might not support presigned URLs
        return {"success": False, "is_local": True}
    except Exception as e:
        print(f"Presigned upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")
