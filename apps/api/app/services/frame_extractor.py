"""
Frame extraction service using OpenCV.
Extracts last frames from video URLs for sequential generation.
"""
import os
import cv2
import tempfile
import httpx
import aiofiles
from typing import List, Optional
import uuid

class FrameExtractor:
    """Service for extracting frames from videos."""
    
    async def extract_last_frame(self, video_url: str) -> str:
        """
        Download video and extract the last frame.
        Returns the path to the saved frame (or uploads to S3 and returns URL in production).
        For now, returns a local path or data URL.
        """
        # Download video to temp file
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_video_path = temp_video.name
        temp_video.close()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(video_url)
                if response.status_code != 200:
                    raise Exception(f"Failed to download video: {response.status_code}")
                
                content = response.content
                async with aiofiles.open(temp_video_path, "wb") as f:
                    await f.write(content)
            
            # Open video with OpenCV
            cap = cv2.VideoCapture(temp_video_path)
            if not cap.isOpened():
                raise Exception("Failed to open video file")
            
            # Get frame count
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Read last frame (or safe last frame - e.g., count - 5)
            # Sometimes the very last frame is empty/black, so we take a few frames back
            target_frame = max(0, frame_count - 5)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                raise Exception("Failed to read frame")
            
            # Save frame to temp file
            # In production, this should upload to S3
            # For MVP, we'll save to static folder or return base64 (if small)
            # Let's verify if we have a static mount. 
            # Assuming we need to return a URL.
            
            # For this MVP, let's assume we have a way to serve static files or we return absolute path
            # But frontend can't access absolute path.
            # So lets convert to Base64 for simplicity in MVP, or upload if upload service exists.
            
            # Actually, `ImageGenerator` likely returns URLs.
            # Let's check if we have S3 configured.
            
            # Fallback: Save to a known static dir served by FastAPI?
            # Or convert to base64 string.
            
            # Let's save to a /tmp directory that is accessible or just Base64.
            # Base64 is safest for MVP without S3.
            
            is_success, buffer = cv2.imencode(".jpg", frame)
            if not is_success:
                raise Exception("Failed to encode frame")
                
            import base64
            base64_str = base64.b64encode(buffer).decode("utf-8")
            return f"data:image/jpeg;base64,{base64_str}"
            
        finally:
            # Cleanup
            if os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
