"""Video Generator Service — fal.ai for all video generation.

Selects the right sub-endpoint (`t2v` / `i2v`) from the model registry based on
inputs. Dispatches through `FalService`:
  * webhook mode (inside a workflow task) → `{status: "pending_fal", request_id}`
  * sync mode (local dev / ad-hoc)        → fetches + uploads to S3, returns final url
"""

from __future__ import annotations

import asyncio
import random
import shutil
import time
from pathlib import Path
from typing import Any, List, Optional

import httpx

from app.core.config import settings
from app.core.dependencies import get_storage_service
from app.core.model_registry import (
    get_model_by_endpoint_id,
    get_model_by_id,
    get_model_by_name,
    resolve_endpoint_id,
)
from app.services.fal_service import FalService

_DEFAULT_VIDEO_ENDPOINT = "fal-ai/kling-video/v3/standard/text-to-video"
_LIPSYNC_ENDPOINT = "fal-ai/kling-video/lipsync/audio-to-video"


class VideoGenerator:
    """Generate video clips via fal.ai endpoints."""

    def __init__(self) -> None:
        self.use_mock = settings.use_mock_veo
        self.storage = get_storage_service()
        self.fal = FalService()
        self.output_dir = Path("static/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.use_mock:
            print("[VideoGenerator] MOCK mode")
        else:
            print("[VideoGenerator] PRODUCTION mode — fal.ai")

    # ------------------------------------------------------------------ Mock
    def _get_mock_video(self) -> Optional[Path]:
        videos = list(self.output_dir.glob("*.mp4"))
        return random.choice(videos) if videos else None

    async def _mock_generate(self, prompt: str, duration: int = 8) -> dict:
        print(f"[VideoGenerator] MOCK: {prompt[:80]}")
        await asyncio.sleep(random.uniform(5, 10))
        mock_source = self._get_mock_video()
        if mock_source:
            filename = f"generated_{int(time.time())}.mp4"
            new_path = self.output_dir / filename
            shutil.copy(mock_source, new_path)
            return {
                "success": True,
                "video_url": f"{settings.api_base_url}/static/videos/{filename}",
                "duration": duration, "model": "mock", "mock": True,
            }
        return {"success": False, "error": "No mock videos available.", "mock": True}

    # ------------------------------------------------------------------ Utils
    async def _fetch_and_upload(self, url: str) -> Optional[str]:
        if not url:
            return None
        print(f"[VideoGenerator] uploading fal video → S3: {url[:80]}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=300.0)
            if response.status_code == 200:
                filename = f"generated_video_{int(time.time())}.mp4"
                return await self.storage.upload_file(response.content, filename, "video/mp4")
            print(f"[VideoGenerator] fetch failed ({response.status_code})")
        except Exception as e:
            print(f"[VideoGenerator] upload failed: {e}")
        return url

    def _resolve_endpoint(self, model_name: Optional[str], *, capability: str) -> tuple[str, dict]:
        endpoint_id = resolve_endpoint_id(
            model_name, _DEFAULT_VIDEO_ENDPOINT, model_type="video", capability=capability,
        )
        entry = get_model_by_endpoint_id(endpoint_id) or get_model_by_id(model_name or "") or {}
        return endpoint_id, entry

    # ------------------------------------------------------------------ Public
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
        generate_audio: bool = False,
        reference_images: Optional[List[str]] = None,
        element_images: Optional[List[str]] = None,
        element_videos: Optional[List[str]] = None,
        element_voices: Optional[List[str]] = None,
        reference_video: Optional[str] = None,
    ) -> dict:
        if self.use_mock:
            return await self._mock_generate(f"[t2v] {prompt}", duration)

        endpoint_id, entry = self._resolve_endpoint(model_name, capability="t2v")
        args = FalService.build_video_args(
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            generate_audio=generate_audio,
            negative_prompt=negative_prompt,
        )
        if reference_images:
            args["image_urls"] = reference_images
            if reference_images:
                args.setdefault("image_url", reference_images[0])
        if reference_video:
            args["video_url"] = reference_video
        if element_images:
            args["elements"] = [{"image_url": url} for url in element_images]
        if element_videos:
            args["element_videos"] = element_videos

        return await self._dispatch_and_finalize(
            capability="t2v", endpoint_id=endpoint_id, args=args, entry=entry,
            model_name_used=model_name, audio_url=audio_url,
            meta={"duration": duration, "resolution": resolution, "aspect_ratio": aspect_ratio},
        )

    async def generate_from_image(
        self,
        prompt: str,
        image_path: str,
        duration: int = 5,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        model_name: Optional[str] = None,
        audio_url: Optional[str] = None,
        end_image_url: Optional[str] = None,
        generate_audio: bool = False,
    ) -> dict:
        if self.use_mock:
            return await self._mock_generate(f"[i2v] {prompt}", duration)

        endpoint_id, entry = self._resolve_endpoint(model_name, capability="i2v")
        args = FalService.build_video_args(
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            image_url=image_path,
            end_image_url=end_image_url,
            generate_audio=generate_audio,
        )
        return await self._dispatch_and_finalize(
            capability="i2v", endpoint_id=endpoint_id, args=args, entry=entry,
            model_name_used=model_name, audio_url=audio_url,
            meta={"duration": duration, "resolution": resolution, "aspect_ratio": aspect_ratio},
        )

    async def generate_with_reference_images(
        self, prompt: str, reference_images: List[str], duration: int = 5,
        resolution: str = "720p", aspect_ratio: str = "16:9",
        model_name: Optional[str] = None, generate_audio: bool = False,
    ) -> dict:
        if not reference_images:
            return {"success": False, "error": "No reference images"}
        return await self.generate_clip(
            prompt=prompt, duration=duration, resolution=resolution,
            aspect_ratio=aspect_ratio, model_name=model_name,
            generate_audio=generate_audio, reference_images=reference_images,
        )

    async def generate_with_elements(
        self, prompt: str,
        element_images: Optional[List[str]] = None,
        element_videos: Optional[List[str]] = None,
        element_voices: Optional[List[str]] = None,
        duration: int = 5, resolution: str = "720p", aspect_ratio: str = "16:9",
        model_name: Optional[str] = None, generate_audio: bool = False,
    ) -> dict:
        if not element_images and not element_videos:
            return {"success": False, "error": "No elements provided"}
        return await self.generate_clip(
            prompt=prompt, duration=duration, resolution=resolution,
            aspect_ratio=aspect_ratio, model_name=model_name,
            generate_audio=generate_audio, element_images=element_images,
            element_videos=element_videos, element_voices=element_voices,
        )

    async def generate_with_interpolation(
        self, prompt: str, first_frame_path: str, last_frame_path: str,
        duration: int = 5, resolution: str = "720p", aspect_ratio: str = "16:9",
        model_name: Optional[str] = None, generate_audio: bool = False,
    ) -> dict:
        return await self.generate_from_image(
            prompt=prompt, image_path=first_frame_path, end_image_url=last_frame_path,
            duration=duration, resolution=resolution, aspect_ratio=aspect_ratio,
            model_name=model_name, generate_audio=generate_audio,
        )

    async def extend_video(
        self, original_video: str, prompt: str,
        duration: int = 5, resolution: str = "720p", aspect_ratio: str = "16:9",
        model_name: Optional[str] = None, audio_url: Optional[str] = None,
        generate_audio: bool = False,
    ) -> dict:
        if not original_video:
            return {"success": False, "error": "No input video provided"}
        return await self.generate_clip(
            prompt=prompt, duration=duration, resolution=resolution,
            aspect_ratio=aspect_ratio, model_name=model_name,
            audio_url=audio_url, generate_audio=generate_audio,
            reference_video=original_video,
        )

    # ------------------------------------------------------------------ Core
    async def _dispatch_and_finalize(
        self, *, capability: str, endpoint_id: str, args: dict, entry: dict,
        model_name_used: Optional[str], audio_url: Optional[str], meta: dict,
    ) -> dict:
        model_info = {
            "name": entry.get("name", endpoint_id),
            "provider": entry.get("provider", "fal.ai"),
        }
        resp = await self.fal.dispatch_for_generator(
            capability=capability, endpoint_id=endpoint_id, arguments=args,
            model_info=model_info, args_meta={**meta, "lipsync_audio_url": audio_url},
        )
        if not resp.get("success"):
            return resp
        if resp.get("status") == "pending_fal":
            return resp

        normalized = FalService.extract_output(capability, resp.get("raw_output"))
        if not normalized.get("success"):
            return normalized

        if audio_url:
            lipsync_resp = await self._apply_lipsync(normalized["video_url"], audio_url)
            if lipsync_resp:
                normalized["video_url"] = lipsync_resp

        normalized["video_url"] = await self._fetch_and_upload(normalized["video_url"]) or normalized["video_url"]
        return await self._with_cost(normalized, endpoint_id, model_info=model_info,
                                     duration_s=meta.get("duration"))

    async def _apply_lipsync(self, video_url: str, audio_url: str) -> Optional[str]:
        """Chain lipsync onto a generated video (sync mode only)."""
        try:
            args = FalService.build_lipsync_args(video_url=video_url, audio_url=audio_url)
            resp = await self.fal.submit(_LIPSYNC_ENDPOINT, args)
            if resp.get("mode") == "sync":
                out = FalService.extract_output("lipsync", resp.get("output"))
                if out.get("success"):
                    return out.get("video_url")
        except Exception as e:
            print(f"[VideoGenerator] lipsync chain failed: {e}")
        return None

    async def _with_cost(
        self, output: dict, endpoint_id: str, *,
        model_info: dict, duration_s: Optional[float] = None,
    ) -> dict:
        from app.core.database import get_database
        from app.services.fal_pricing import FalPricingService

        try:
            pricing = FalPricingService(get_database())
            cost_info = await pricing.compute_cost_usd(endpoint_id, duration_s=duration_s)
            output["cost"] = cost_info["cost_usd"]
        except Exception as e:
            print(f"[VideoGenerator] cost calc failed: {e}")
            output["cost"] = 0.0
        output["model"] = model_info.get("name")
        output["provider"] = model_info.get("provider")
        return output
