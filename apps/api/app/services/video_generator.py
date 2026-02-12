"""Video Generator Service - Uses Google Veo 3.1 for video generation."""

import asyncio
import base64
import os
import random
import shutil
import time
import tempfile
from pathlib import Path
from typing import Optional, List

import httpx
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.dependencies import get_storage_service


def _veo_error_message(exc: Exception) -> str:
    """Turn Veo API errors into a clear message for the user."""
    msg = str(exc).lower()
    if "invalid_argument" in msg or "use case is currently not supported" in msg:
        return (
            f"Veo error: {exc}\n\n"
            "Veo video generation is in preview and may require specific allowlist access. "
            "Ensure you are not requesting 'allow_all' for person generation unless you have specific child safety clearance. "
            "Set USE_MOCK_VEO=true in .env to use mock mode (returns a sample video), "
            "or request Veo access: https://ai.google.dev/gemini-api/docs/video"
        )
    return str(exc)


class VideoGenerator:
    """Generates video clips using Google Veo 3.1 (or mock mode for development)."""

    def __init__(self):
        self.use_mock = settings.use_mock_veo
        self.storage = get_storage_service()
        
        # Ensure output directory exists (still needed for mock/temp?)
        self.output_dir = Path("static/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.use_mock:
            print("[VideoGenerator] Running in MOCK mode - no API calls will be made")
            self.client = None
        else:
            # Set API key in environment for SDK auto-pickup
            if settings.google_ai_key:
                os.environ["GEMINI_API_KEY"] = settings.google_ai_key
            
            # Client auto-picks GEMINI_API_KEY from environment
            self.client = genai.Client()
            print("[VideoGenerator] Running in PRODUCTION mode - using real Veo API")
        
        self.model = "veo-3.1-generate-preview"
        self.fast_model = "veo-3.1-fast-generate-preview"

    def _get_mock_video(self) -> Optional[Path]:
        """Get a random existing video from static/videos for mock mode."""
        videos = list(self.output_dir.glob("*.mp4"))
        if videos:
            return random.choice(videos)
        return None

    async def _mock_generate(self, prompt: str, duration: int = 8) -> dict:
        """
        Mock video generation - simulates delay and returns existing video.
        """
        print(f"[VideoGenerator] MOCK: Simulating generation for prompt: {prompt[:80]}...")
        
        # Simulate generation delay (5-15 seconds instead of minutes)
        delay = random.uniform(5, 15)
        for i in range(int(delay)):
            print(f"[VideoGenerator] MOCK: Generating... ({i+1}/{int(delay)}s)")
            await asyncio.sleep(1)
        
        # Get an existing mock video or create a placeholder
        mock_source = self._get_mock_video()
        
        if mock_source:
            # Copy the mock video with a new filename
            filename = f"generated_{int(time.time())}.mp4"
            new_path = self.output_dir / filename
            shutil.copy(mock_source, new_path)
            
            video_url = f"{settings.api_base_url}/static/videos/{filename}"
            print(f"[VideoGenerator] MOCK: Generated (copied from {mock_source.name}): {video_url}")
            
            return {
                "success": True,
                "video_url": video_url,
                "duration": duration,
                "model": "mock-veo-3.1",
                "mock": True,
            }
        else:
            # No mock videos available
            print("[VideoGenerator] MOCK: No existing videos to use as mock")
            return {
                "success": False,
                "error": "No mock videos available in static/videos. Add an .mp4 file there.",
                "mock": True,
            }

    async def _fetch_image_to_temp(self, url: str) -> Optional[str]:
        """Fetch image from URL and save to temporary file, return temp path."""
        if not url:
            return None
        
        try:
            # If it's already a local file path, return it
            if os.path.exists(url):
                return url
            
            # Download from URL
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                if response.status_code == 200:
                    # Create temp file with appropriate extension
                    suffix = ".png" if url.lower().endswith(".png") else ".jpg"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(response.content)
                        temp_path = tmp.name
                    
                    print(f"[VideoGenerator] Downloaded image to temp file: {temp_path}")
                    return temp_path
                
                print(f"[VideoGenerator] Failed to fetch image {url}: status {response.status_code}")
        except Exception as e:
            print(f"[VideoGenerator] Error fetching image {url}: {e}")
        
        return None

    async def generate_clip(
        self,
        prompt: str,
        duration: int = 8,
        use_fast_model: bool = False,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        negative_prompt: Optional[str] = None,
    ) -> dict:
        """
        Generate a video clip from a text prompt.
        
        Args:
            prompt: Detailed description of the video to generate
            duration: Duration in seconds (4, 6, or 8 for Veo 3.1)
            use_fast_model: Use the faster model for quicker generation
            resolution: "720p" or "1080p" (1080p only supports 8s duration)
            aspect_ratio: "16:9" or "9:16"
            negative_prompt: Text describing what NOT to include
            
        Returns:
            Dictionary with video URL and metadata
        """
        # Use mock mode if enabled
        if self.use_mock:
            return await self._mock_generate(prompt, duration)
        
        model = self.fast_model if use_fast_model else self.model
        
        # Validate duration
        valid_durations = [4, 6, 8]
        duration = min(duration, 8)
        if duration not in valid_durations:
            duration = 8
        
        # 1080p only supports 8s duration
        if resolution == "1080p" and duration != 8:
            duration = 8
        
        try:
            # Build config (duration_seconds: 4, 6, or 8; resolution: 720p or 1080p per Veo 3.1 API)
            config = types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                person_generation="allow_adult",
                duration_seconds=duration,
                resolution=resolution,
            )
            
            if negative_prompt:
                config.negative_prompt = negative_prompt

            # Start video generation
            operation = self.client.models.generate_videos(
                model=model,
                prompt=prompt,
                config=config,
            )

            # Poll for completion (async)
            result = await self._poll_operation(operation)
            
            if result and result.generated_videos:
                video = result.generated_videos[0]
                
                # Download and save the video
                video_url = await self._save_video(video)
                
                return {
                    "success": True,
                    "video_url": video_url,
                    "duration": duration,
                    "model": model,
                }
            
            return {
                "success": False,
                "error": "No video generated",
            }

        except Exception as e:
            err_msg = _veo_error_message(e)
            print(f"[VideoGenerator] Error: {e}")
            return {
                "success": False,
                "error": err_msg,
            }

    async def _poll_operation(self, operation, timeout: int = 600, poll_interval: int = 10):
        """
        Poll the operation until complete or timeout.
        """
        start_time = time.time()
        
        while not operation.done:
            if time.time() - start_time > timeout:
                raise TimeoutError("Video generation timed out")
            
            print(f"[VideoGenerator] Waiting for video generation... ({int(time.time() - start_time)}s)")
            await asyncio.sleep(poll_interval)
            
            # Refresh the operation object to get latest status
            operation = self.client.operations.get(operation)
        
        return operation.response

    async def _save_video(self, generated_video) -> Optional[str]:
        """
        Download the generated video and save to StorageService.
        """
        try:
            # Download the video file from Google
            # self.client.files.download(file=generated_video.video) 
            # The SDK download method might write to a file or return bytes? 
            # Looking at code: generated_video.video.save(path) suggests it handles saving.
            # We probably need to save to a temp file first then upload.
            
            # Create a temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                temp_path = Path(tmp.name)
            
            # Save to temp path using SDK
            # Note: The original code called self.client.files.download() then .save().
            # Depending on SDK version, .download() might just be a trigger or ensure it's available?
            # We will follow the pattern:
            # Check if we need to call download() - assumed yes based on existing code
            try:
                self.client.files.download(file=generated_video.video)
            except Exception as e:
                print(f"[VideoGenerator] Warning: ensure download failed or not needed: {e}")

            generated_video.video.save(str(temp_path))
            print(f"[VideoGenerator] Video saved to temp: {temp_path}")
            
            # Read bytes
            with open(temp_path, "rb") as f:
                video_data = f.read()
            
            # Remove temp file
            os.remove(temp_path)
            
            # Upload
            filename = f"generated_{int(time.time())}.mp4"
            video_url = await self.storage.upload_file(video_data, filename, "video/mp4")
            
            return video_url
            
        except Exception as e:
            print(f"[VideoGenerator] Video save error: {e}")
            return None

    async def generate_from_image(
        self,
        prompt: str,
        image_path: str,
        duration: int = 8,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
    ) -> dict:
        """Generate video using an image as the starting frame."""
        if self.use_mock:
            return await self._mock_generate(f"[Image-to-Video] {prompt}", duration)
        
        try:
            # Fetch image if it's a URL
            local_path = await self._fetch_image_to_temp(image_path)
            if not local_path:
                return {"success": False, "error": "Failed to fetch start image"}
            
            # Read image as raw bytes
            with open(local_path, 'rb') as f:
                image_bytes = f.read()
            
            mime_type = "image/png" if local_path.lower().endswith(".png") else "image/jpeg"
            
            # Create Image object with correct fields
            image = types.Image(
                image_bytes=image_bytes,
                mime_type=mime_type
            )
            
            config = types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                person_generation="allow_adult",
                duration_seconds=duration,
                resolution=resolution,
            )

            operation = self.client.models.generate_videos(
                model=self.fast_model,
                prompt=prompt,
                image=image,
                config=config,
            )

            result = await self._poll_operation(operation)
            
            if result and result.generated_videos:
                video = result.generated_videos[0]
                video_url = await self._save_video(video)
                
                return {"success": True, "video_url": video_url, "duration": duration}
            
            return {"success": False, "error": "No video generated"}

        except Exception as e:
            err_msg = _veo_error_message(e)
            print(f"[VideoGenerator] Image-to-video error: {e}")
            return {"success": False, "error": err_msg}

    async def generate_with_reference_images(
        self,
        prompt: str,
        reference_images: List[str],
        duration: int = 8,
        aspect_ratio: str = "16:9",
    ) -> dict:
        """Generate video using reference images (Veo 3.1 only)."""
        if self.use_mock:
            return await self._mock_generate(f"[Reference Images] {prompt}", duration)
        
        try:
            refs = []
            for img_path in reference_images[:3]:
                local_path = await self._fetch_image_to_temp(img_path)
                if local_path:
                    # Read image as raw bytes
                    with open(local_path, 'rb') as f:
                        img_bytes = f.read()
                    
                    mime_type = "image/png" if local_path.lower().endswith(".png") else "image/jpeg"
                    
                    # Create Image object
                    image = types.Image(
                        image_bytes=img_bytes,
                        mime_type=mime_type
                    )
                    
                    ref = types.VideoGenerationReferenceImage(
                        image=image,
                        reference_type="asset"
                    )
                    refs.append(ref)
            
            if not refs:
                return {"success": False, "error": "Failed to fetch reference images"}
            
            config = types.GenerateVideosConfig(
                reference_images=refs,
                aspect_ratio=aspect_ratio,
                person_generation="allow_adult",
                duration_seconds=duration,
            )

            operation = self.client.models.generate_videos(
                model=self.fast_model,
                prompt=prompt,
                config=config,
            )

            result = await self._poll_operation(operation)
            
            if result and result.generated_videos:
                video = result.generated_videos[0]
                video_url = await self._save_video(video)
                
                return {"success": True, "video_url": video_url}
            
            return {"success": False, "error": "No video generated"}

        except Exception as e:
            err_msg = _veo_error_message(e)
            print(f"[VideoGenerator] Reference images error: {e}")
            return {"success": False, "error": err_msg}

    async def generate_with_interpolation(
        self,
        prompt: str,
        first_frame_path: str,
        last_frame_path: str,
        duration: int = 8,
    ) -> dict:
        """Generate video by specifying first and last frames (Veo 3.1 only)."""
        if self.use_mock:
            return await self._mock_generate(f"[Interpolation] {prompt}", duration)
        
        try:
            # Fetch images if they're URLs
            first_local = await self._fetch_image_to_temp(first_frame_path)
            last_local = await self._fetch_image_to_temp(last_frame_path)
            
            if not first_local or not last_local:
                return {"success": False, "error": "Failed to fetch start or end image"}
            
            # Read first image as raw bytes
            with open(first_local, 'rb') as f:
                first_bytes = f.read()
            first_mime = "image/png" if first_local.lower().endswith(".png") else "image/jpeg"
            
            # Read last image as raw bytes
            with open(last_local, 'rb') as f:
                last_bytes = f.read()
            last_mime = "image/png" if last_local.lower().endswith(".png") else "image/jpeg"
            
            # Create Image objects with correct fields
            first_image = types.Image(
                image_bytes=first_bytes,
                mime_type=first_mime
            )
            last_image = types.Image(
                image_bytes=last_bytes,
                mime_type=last_mime
            )
            
            config = types.GenerateVideosConfig(
                last_frame=last_image,
                person_generation="allow_adult",
                duration_seconds=duration,
            )

            operation = self.client.models.generate_videos(
                model=self.fast_model,
                prompt=prompt,
                image=first_image,
                config=config,
            )

            result = await self._poll_operation(operation)
            
            if result and result.generated_videos:
                video = result.generated_videos[0]
                video_url = await self._save_video(video)
                
                return {"success": True, "video_url": video_url}
            
            return {"success": False, "error": "No video generated"}

        except Exception as e:
            err_msg = _veo_error_message(e)
            print(f"[VideoGenerator] Interpolation error: {e}")
            return {"success": False, "error": err_msg}

    async def extend_video(
        self,
        original_video,
        prompt: str,
        resolution: str = "720p",
    ) -> dict:
        """Extend a previously generated Veo video (Veo 3.1 only)."""
        if self.use_mock:
            return await self._mock_generate(f"[Extension] {prompt}", 8)
        
        try:
            config = types.GenerateVideosConfig(
                number_of_videos=1,
                resolution="720p",
            )

            operation = self.client.models.generate_videos(
                model=self.model,
                video=original_video,
                prompt=prompt,
                config=config,
            )

            result = await self._poll_operation(operation)
            
            if result and result.generated_videos:
                video = result.generated_videos[0]
                video_url = await self._save_video(video)
                
                return {"success": True, "video_url": video_url}
            
            return {"success": False, "error": "No video generated"}

        except Exception as e:
            err_msg = _veo_error_message(e)
            print(f"[VideoGenerator] Extension error: {e}")
            return {"success": False, "error": err_msg}
