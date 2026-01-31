"""Video Generator Service - Uses Google Veo 3.1 for video generation."""

import asyncio
import os
import random
import shutil
import time
from pathlib import Path
from typing import Optional, List

import boto3
from botocore.exceptions import ClientError
from google import genai
from google.genai import types

from app.core.config import settings


class VideoGenerator:
    """Generates video clips using Google Veo 3.1 (or mock mode for development)."""

    def __init__(self):
        self.use_mock = settings.use_mock_veo
        
        # Ensure output directory exists
        self.output_dir = Path("static/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.use_mock:
            print("[VideoGenerator] Running in MOCK mode - no API calls will be made")
            self.client = None
        else:
            # Set API key in environment for SDK auto-pickup
            if settings.gemini_api_key:
                os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
            
            # Client auto-picks GEMINI_API_KEY from environment
            self.client = genai.Client()
            print("[VideoGenerator] Running in PRODUCTION mode - using real Veo API")
        
        self.model = "veo-3.1-generate-preview"
        self.fast_model = "veo-3.1-fast-generate-preview"
        
        # Initialize S3 client if credentials are available
        self.s3_client = None
        self.use_s3 = bool(
            settings.aws_access_key_id 
            and settings.aws_secret_access_key 
            and settings.s3_bucket
            and not settings.aws_access_key_id.startswith("#")  # Ignore comments
        )
        
        if self.use_s3:
            try:
                s3_config = {
                    "aws_access_key_id": settings.aws_access_key_id,
                    "aws_secret_access_key": settings.aws_secret_access_key,
                    "region_name": settings.aws_region,
                }
                # Only add endpoint if it's a valid URL (not empty or a comment)
                if settings.s3_endpoint and settings.s3_endpoint.startswith("http"):
                    s3_config["endpoint_url"] = settings.s3_endpoint
                
                self.s3_client = boto3.client("s3", **s3_config)
                print(f"[VideoGenerator] S3 configured: bucket={settings.s3_bucket}")
            except Exception as e:
                print(f"[VideoGenerator] S3 initialization failed: {e}, using local storage")
                self.use_s3 = False
                self.s3_client = None

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
            # Build config
            config = types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                person_generation="allow_all",
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
            print(f"[VideoGenerator] Error: {e}")
            return {
                "success": False,
                "error": str(e),
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
        Download the generated video and save to S3 or local disk.
        """
        try:
            # Download the video file from Google
            self.client.files.download(file=generated_video.video)
            
            # Generate unique filename
            filename = f"generated_{int(time.time())}.mp4"
            local_path = self.output_dir / filename
            
            # Save locally first
            generated_video.video.save(str(local_path))
            print(f"[VideoGenerator] Video saved locally: {local_path}")
            
            # Upload to S3 if configured
            if self.use_s3 and self.s3_client:
                s3_key = f"videos/{filename}"
                video_url = await self._upload_to_s3(local_path, s3_key)
                
                if video_url:
                    return video_url
            
            # Return local URL (via API static files)
            return f"{settings.api_base_url}/static/videos/{filename}"
            
        except Exception as e:
            print(f"[VideoGenerator] Video save error: {e}")
            return None

    async def _upload_to_s3(self, local_path: Path, s3_key: str) -> Optional[str]:
        """
        Upload a video file to S3 and return a presigned URL.
        """
        try:
            self.s3_client.upload_file(
                str(local_path),
                settings.s3_bucket,
                s3_key,
                ExtraArgs={"ContentType": "video/mp4"}
            )
            
            # Generate presigned URL (valid for 7 days)
            video_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.s3_bucket,
                    "Key": s3_key,
                },
                ExpiresIn=7 * 24 * 60 * 60,  # 7 days in seconds
            )
            
            print(f"[VideoGenerator] Video uploaded to S3: {s3_key}")
            return video_url
            
        except ClientError as e:
            print(f"[VideoGenerator] S3 upload error: {e}")
            return None
    
    def get_presigned_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a new presigned URL for an existing S3 object.
        
        Args:
            s3_key: The S3 object key (e.g., "videos/generated_123.mp4")
            expires_in: URL expiration time in seconds (default 1 hour)
        """
        if not self.use_s3 or not self.s3_client:
            return None
        
        try:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.s3_bucket,
                    "Key": s3_key,
                },
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            print(f"[VideoGenerator] Presigned URL error: {e}")
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
            image = types.Image.from_file(image_path)
            
            config = types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                person_generation="allow_adult",
            )

            operation = self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                image=image,
                config=config,
            )

            result = await self._poll_operation(operation)
            
            if result and result.generated_videos:
                video = result.generated_videos[0]
                video_url = await self._save_video(video)
                
                return {"success": True, "video_url": video_url}
            
            return {"success": False, "error": "No video generated"}

        except Exception as e:
            print(f"[VideoGenerator] Image-to-video error: {e}")
            return {"success": False, "error": str(e)}

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
                image = types.Image.from_file(img_path)
                ref = types.VideoGenerationReferenceImage(
                    image=image,
                    reference_type="asset"
                )
                refs.append(ref)
            
            config = types.GenerateVideosConfig(
                reference_images=refs,
                aspect_ratio="16:9",
                person_generation="allow_adult",
            )

            operation = self.client.models.generate_videos(
                model=self.model,
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
            print(f"[VideoGenerator] Reference images error: {e}")
            return {"success": False, "error": str(e)}

    async def generate_with_interpolation(
        self,
        prompt: str,
        first_frame_path: str,
        last_frame_path: str,
    ) -> dict:
        """Generate video by specifying first and last frames (Veo 3.1 only)."""
        if self.use_mock:
            return await self._mock_generate(f"[Interpolation] {prompt}", 8)
        
        try:
            first_image = types.Image.from_file(first_frame_path)
            last_image = types.Image.from_file(last_frame_path)
            
            config = types.GenerateVideosConfig(
                last_frame=last_image,
                person_generation="allow_adult",
            )

            operation = self.client.models.generate_videos(
                model=self.model,
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
            print(f"[VideoGenerator] Interpolation error: {e}")
            return {"success": False, "error": str(e)}

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
            print(f"[VideoGenerator] Extension error: {e}")
            return {"success": False, "error": str(e)}
