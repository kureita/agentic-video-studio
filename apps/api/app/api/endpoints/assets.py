import os
import shutil
import uuid
from typing import Dict, Any

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from app.core.config import settings
from app.services.storage_service import StorageService
from app.core.dependencies import get_storage_service

router = APIRouter()

@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
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
        
        return {
            "success": True,
            "filename": file.filename,
            "url": file_url,
            "type": file.content_type
        }
        
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
