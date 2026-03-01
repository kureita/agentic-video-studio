"""Video Generator Service - Uses Runware API for video generation."""

import asyncio
import os
import random
import shutil
import time
import httpx
from pathlib import Path
from typing import Optional, List

from app.core.config import settings
from app.core.dependencies import get_storage_service
from app.services.runware_service import RunwareService

_MODEL_MAP = {
    # Frontend display name → Official Runware AIR ID (provider:model@version)

    # Google Veo — https://docs.runware.ai/en/providers/google
    "Veo 3.1":              "google:3@2",
    "Veo 3.1 Fast":         "google:3@3",
    "Veo 3":                "google:3@0",
    "Veo 3 Fast":           "google:3@1",
    "Veo 2":                "google:2@0",

    # KlingAI — https://docs.runware.ai/en/providers/klingai
    "Kling 3.0 Standard":   "klingai:kling-video@3-standard",
    "Kling 3.0 Pro":        "klingai:kling-video@3-pro",
    "Kling 2.1 Master":     "klingai:5@3",
    "Kling Lip Sync":       "__lipsync__",   # Sentinel → klingai:7@1

    # Runway — https://docs.runware.ai/en/providers/runway
    "Runway Gen-4.5":       "runway:1@2",
    "Runway Gen-4 Turbo":   "runway:1@1",

    # ByteDance Seedance — https://docs.runware.ai/en/providers/bytedance
    "Seedance 1.5 Pro":     "bytedance:seedance@1.5-pro",
    "Seedance 1.0 Pro":     "bytedance:2@1",
    "Seedance 1.0 Pro Fast":"bytedance:2@2",
    "Seedance 1.0 Lite":    "bytedance:1@1",

    # Alibaba Wan — https://docs.runware.ai/en/providers/alibaba
    "Wan2.6":               "alibaba:wan@2.6",
    "Wan2.6 Flash":         "alibaba:wan@2.6-flash",

    # MiniMax Hailuo — https://docs.runware.ai/en/providers/minimax
    "Hailuo 2.3":           "minimax:4@1",
    "Hailuo 2.3 Fast":      "minimax:4@2",

    # PixVerse — https://docs.runware.ai/en/providers/pixverse
    "PixVerse V5.6":        "pixverse:1@7",

    # Legacy names (backward compat)
    "Veo":                  "google:3@3",
    "Kling":                "klingai:kling-video@3-standard",
    "Kling V1.5":           "klingai:kling-video@3-standard",
    "Kling V1.0":           "klingai:kling-video@3-standard",
    "SeedDance 1.5 Pro":    "bytedance:seedance@1.5-pro",
    "SeedDance 1.0 Pro":    "bytedance:2@1",
}


class VideoGenerator:
    """Generates video clips using Runware API (Kling, Runway, PixVerse, etc)."""

    def __init__(self):
        self.use_mock = settings.use_mock_veo
        self.storage = get_storage_service()
        self.runware = RunwareService()
        
        self.output_dir = Path("static/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.use_mock:
            print("[VideoGenerator] Running in MOCK mode - no API calls")
        else:
            print("[VideoGenerator] Running in PRODUCTION mode - using Runware API")
        
        self.default_model = "klingai-video-3-0-standard"

    def _get_mock_video(self) -> Optional[Path]:
        """Get a random existing video from static/videos for mock mode."""
        videos = list(self.output_dir.glob("*.mp4"))
        if videos:
            return random.choice(videos)
        return None

    async def _mock_generate(self, prompt: str, duration: int = 8) -> dict:
        """Mock video generation."""
        print(f"[VideoGenerator] MOCK: Simulating generation for prompt: {prompt[:80]}...")
        
        delay = random.uniform(5, 10)
        await asyncio.sleep(delay)
        
        mock_source = self._get_mock_video()
        
        if mock_source:
            filename = f"generated_{int(time.time())}.mp4"
            new_path = self.output_dir / filename
            shutil.copy(mock_source, new_path)
            
            video_url = f"{settings.api_base_url}/static/videos/{filename}"
            print(f"[VideoGenerator] MOCK: Generated (copied from {mock_source.name}): {video_url}")
            
            return {
                "success": True,
                "video_url": video_url,
                "duration": duration,
                "model": "mock",
                "mock": True,
            }
        else:
            return {
                "success": False,
                "error": "No mock videos available in static/videos.",
                "mock": True,
            }

    async def _fetch_and_upload(self, url: str) -> Optional[str]:
        """Fetch file from URL and save to StorageService, returning the storage URL."""
        if not url: return None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=300.0)
                if response.status_code == 200:
                    filename = f"generated_video_{int(time.time())}.mp4"
                    storage_url = await self.storage.upload_file(response.content, filename, "video/mp4")
                    return storage_url
        except Exception as e:
            print(f"[VideoGenerator] Error fetching video {url}: {e}")
        return url # fallback to runware url

    def _get_model(self, model_name: Optional[str]) -> str:
        """Map frontend model display name to Runware internal ID.
        Returns '__lipsync__' sentinel for Kling Lip Sync so callers can route correctly.
        """
        if not model_name:
            return self.default_model
        # Exact match first
        if model_name in _MODEL_MAP:
            return _MODEL_MAP[model_name]
        # Substring fallback for any legacy names
        for key, val in _MODEL_MAP.items():
            if key in model_name or model_name in key:
                return val
        return self.default_model


    async def generate_clip(
        self,
        prompt: str,
        duration: int = 5,
        use_fast_model: bool = False,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        negative_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        audio_url: Optional[str] = None,
    ) -> dict:
        """Generate a video clip from a text prompt."""
        if self.use_mock:
            return await self._mock_generate(f"[Text-to-Vid] {prompt}", duration)
        
        target_model = self._get_model(model_name)
        
        # Kling Lip Sync sentinel — lipsync requires an input video/image + audio, not text-to-video
        if target_model == "__lipsync__":
            return {"success": False, "error": "Kling Lip Sync requires a Start Image/Video and an Audio input. Please connect those inputs to the node."}
            
        print(f"[VideoGenerator] Generating video with {target_model}: {prompt[:100]}")
        
        try:
            result = await self.runware.generate_video(
                prompt=prompt,
                model=target_model,
                duration=duration,
                aspect_ratio=aspect_ratio
            )
            
            # Optionally add lip-sync if audio_url provided and supported
            if result.get("success") and audio_url:
                print(f"[VideoGenerator] Proceeding to lipsync with audio: {audio_url}")
                sync_resp = await self.runware.lipsync(
                    video_url=result["video_url"],
                    audio_url=audio_url
                )
                if sync_resp.get("success"):
                    result["video_url"] = sync_resp["video_url"]
                    
            if result.get("success"):
                final_url = await self._fetch_and_upload(result.get("video_url"))
                result["video_url"] = final_url
                
            return result
            
        except Exception as e:
            print(f"[VideoGenerator] Error: {e}")
            return {"success": False, "error": str(e)}

    async def generate_from_image(
        self,
        prompt: str,
        image_path: str,
        duration: int = 5,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        model_name: Optional[str] = None,
        audio_url: Optional[str] = None,
    ) -> dict:
        """Generate video using an image as the starting frame."""
        if self.use_mock:
            return await self._mock_generate(f"[Image-to-Video] {prompt}", duration)
            
        target_model = self._get_model(model_name)
        print(f"[VideoGenerator] Generating img-to-vid with {target_model}: {prompt[:100]}")

        try:
            # First frame provided
            result = await self.runware.image_to_video(
                image_url=image_path,
                prompt=prompt,
                model=target_model,
                duration=duration,
            )
            
            # Optionally add lip-sync
            if result.get("success") and audio_url:
                sync_resp = await self.runware.lipsync(
                    video_url=result["video_url"],
                    audio_url=audio_url
                )
                if sync_resp.get("success"):
                    result["video_url"] = sync_resp["video_url"]

            if result.get("success"):
                final_url = await self._fetch_and_upload(result.get("video_url"))
                result["video_url"] = final_url
                
            return result
            
        except Exception as e:
            print(f"[VideoGenerator] Error: {e}")
            return {"success": False, "error": str(e)}

    async def generate_with_reference_images(
        self,
        prompt: str,
        reference_images: List[str],
        duration: int = 5,
        aspect_ratio: str = "16:9",
        model_name: Optional[str] = None,
    ) -> dict:
        """Generate video using reference images."""
        if not reference_images:
            return {"success": False, "error": "No reference images"}
        
        # We can just use the first image for image-to-video for now, 
        # or map to a Runware model that accepts multiple images if any.
        return await self.generate_from_image(
            prompt=prompt,
            image_path=reference_images[0],
            duration=duration,
            aspect_ratio=aspect_ratio,
            model_name=model_name
        )

    async def generate_with_interpolation(
        self,
        prompt: str,
        first_frame_path: str,
        last_frame_path: str,
        duration: int = 5,
        model_name: Optional[str] = None,
    ) -> dict:
        """Generate video by specifying first and last frames."""
        print("[VideoGenerator] Runware does not currently support explicit end-frame natively in standard tasks, using first frame.")
        return await self.generate_from_image(
            prompt=prompt,
            image_path=first_frame_path,
            duration=duration,
            model_name=model_name
        )

    async def extend_video(
        self,
        original_video,
        prompt: str,
        resolution: str = "720p",
    ) -> dict:
        """Extend a previously generated video."""
        return {"success": False, "error": "Video extension not natively supported yet via wrapper"}
