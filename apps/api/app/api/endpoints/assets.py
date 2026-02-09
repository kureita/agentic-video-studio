import os
import shutil
import uuid
from typing import Dict, Any

from fastapi import APIRouter, File, UploadFile, HTTPException
from app.core.config import settings

router = APIRouter()

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_asset(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Upload an asset file (image/video/audio).
    Returns the URL to the uploaded file.
    """
    try:
        # Generate unique filename to prevent collisions
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Construct URL
        # Assuming static files are served from /static
        # If running locally with specialized port, usage might vary, but relative path is safest
        # or full URL if settings.api_base_url is available
        
        # Use relative path for flexibility, or absolute if needed by frontend
        # For now return absolute URL if base_url is set, else relative
        
        base_url = settings.api_base_url or ""
        # Ensure no double slash
        if base_url.endswith("/"):
            base_url = base_url[:-1]
            
        file_url = f"{base_url}/static/uploads/{unique_filename}"
        
        return {
            "success": True,
            "filename": file.filename,
            "url": file_url,
            "type": file.content_type
        }
        
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
