"""Image Generator Service — fal.ai for all image generation.

The generator dispatches through `FalService`:
  * When running inside a workflow task (fal_webhook_context is set) and
    `FAL_WEBHOOK_PUBLIC_URL` is configured, returns `{status: "pending_fal", request_id}`.
  * Otherwise runs synchronously (fal_client.subscribe_async) and returns the final result.
"""

from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path
from typing import Any, Optional

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


_DEFAULT_IMAGE_ENDPOINT = "fal-ai/nano-banana-2"


class ImageGenerator:
    """Generate images via fal.ai endpoints selected from the featured model registry."""

    def __init__(self) -> None:
        self.use_mock = settings.use_mock_veo
        self.storage = get_storage_service()
        self.fal = FalService()

        if self.use_mock:
            print("[ImageGenerator] MOCK mode — no API calls")
        else:
            print("[ImageGenerator] PRODUCTION mode — fal.ai")

    # ------------------------------------------------------------------ Mock
    def _get_mock_image(self) -> Optional[Path]:
        try:
            output_dir = Path("static/images")
            if output_dir.exists():
                images = list(output_dir.glob("*.png")) + list(output_dir.glob("*.jpg"))
                if images:
                    return random.choice(images)
        except Exception:
            pass
        return None

    async def _mock_generate(self, prompt: str) -> dict:
        print(f"[ImageGenerator] MOCK: {prompt[:80]}...")
        await asyncio.sleep(random.uniform(2, 5))
        mock_source = self._get_mock_image()
        if mock_source:
            try:
                with open(mock_source, "rb") as f:
                    content = f.read()
                filename = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
                image_url = await self.storage.upload_file(content, filename, "image/png")
                return {"success": True, "image_url": image_url, "prompt": prompt, "mock": True}
            except Exception as e:
                print(f"[ImageGenerator] Mock upload failed: {e}")
                return {
                    "success": True,
                    "image_url": f"{settings.api_base_url}/static/images/{mock_source.name}",
                    "prompt": prompt,
                    "mock": True,
                }
        return {
            "success": True,
            "image_url": f"https://picsum.photos/seed/{int(time.time())}/1344/768",
            "prompt": prompt,
            "mock": True,
        }

    # ------------------------------------------------------------------ Utils
    async def _fetch_image(self, url: str) -> Optional[bytes]:
        if not url:
            return None
        try:
            if url.startswith("data:"):
                import base64
                if ";base64," in url:
                    return base64.b64decode(url.split(";base64,")[1])
                return None
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=60.0)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            print(f"[ImageGenerator] fetch error {url[:80]}: {e}")
        return None

    def _check_i2i_support(self, model_name: Optional[str]) -> tuple[bool, str]:
        if not model_name:
            return True, "default"
        entry = get_model_by_id(model_name) or get_model_by_name(model_name) or get_model_by_endpoint_id(model_name)
        if not entry:
            return True, model_name
        caps = [c.lower() for c in entry.get("capabilities", [])]
        return "i2i" in caps, entry.get("name", model_name)

    # ------------------------------------------------------------------ Public
    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        style: str = "realistic",
        reference_image: Optional[Any] = None,
        model_name: Optional[str] = None,
    ) -> dict:
        if self.use_mock:
            return await self._mock_generate(prompt)

        capability = "i2i" if reference_image else "t2i"

        if reference_image:
            supports_i2i, display = self._check_i2i_support(model_name)
            if not supports_i2i:
                return {
                    "success": False,
                    "error": (
                        f"'{display}' does not support reference images (image-to-image). "
                        f"Switch to a model that supports it."
                    ),
                }

        endpoint_id = resolve_endpoint_id(
            model_name, _DEFAULT_IMAGE_ENDPOINT, model_type="image", capability=capability,
        )
        entry = get_model_by_endpoint_id(endpoint_id) or get_model_by_id(model_name or "") or {}

        style_suffix = {
            "realistic": "photorealistic, high detail, professional photography",
            "cinematic": "cinematic lighting, movie still, dramatic composition",
            "animated": "3D animation style, Pixar quality, vibrant colors",
            "cartoon": "illustrated style, colorful cartoon, clean lines",
            "minimalist": "minimal design, clean aesthetic, simple composition",
            "dramatic": "high contrast, bold lighting, intense atmosphere",
        }.get(style, "photorealistic, high detail, professional photography")
        enhanced_prompt = f"{prompt}. {style_suffix}" if prompt else prompt
        if reference_image and enhanced_prompt:
            enhanced_prompt = f"Based on the provided reference image: {enhanced_prompt}"

        reference_urls: Optional[list[str]] = None
        if reference_image:
            if isinstance(reference_image, list):
                reference_urls = [x for x in reference_image if isinstance(x, str) and x]
            elif isinstance(reference_image, str) and reference_image:
                reference_urls = [reference_image]

        args = FalService.build_image_args(
            prompt=enhanced_prompt or "",
            aspect_ratio=aspect_ratio,
            reference_image_urls=reference_urls,
        )

        print(f"[ImageGenerator] endpoint={endpoint_id} ratio={aspect_ratio} ref={bool(reference_urls)}")

        model_info = {
            "name": entry.get("name", endpoint_id),
            "provider": entry.get("provider", "fal.ai"),
        }

        resp = await self.fal.dispatch_for_generator(
            capability=capability,
            endpoint_id=endpoint_id,
            arguments=args,
            model_info=model_info,
            args_meta={"aspect_ratio": aspect_ratio, "style": style},
        )
        if not resp.get("success"):
            return resp
        if resp.get("status") == "pending_fal":
            return resp

        normalized = FalService.extract_output(capability, resp.get("raw_output"))
        if not normalized.get("success"):
            return normalized

        img_bytes = await self._fetch_image(normalized["image_url"])
        if img_bytes:
            filename = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
            normalized["image_url"] = await self.storage.upload_file(img_bytes, filename, "image/png")

        return await self._with_cost(normalized, endpoint_id, model_info=model_info)

    async def generate_scene_images(
        self, scenes: list, visual_style: str = "realistic", aspect_ratio: str = "16:9",
    ) -> list:
        results = []
        for idx, scene in enumerate(scenes):
            print(f"[ImageGenerator] scene {idx+1}/{len(scenes)}")
            visual_prompt = scene.get("visual_prompt", "") or scene.get("description", "")
            image_prompt = self._build_image_prompt(visual_prompt, visual_style)
            result = await self.generate_image(
                prompt=image_prompt, aspect_ratio=aspect_ratio, style=visual_style,
            )
            scene_result = dict(scene)
            scene_result["image_prompt"] = image_prompt
            if result.get("success"):
                scene_result["image_url"] = result.get("image_url")
            results.append(scene_result)
        return results

    def _build_image_prompt(self, visual_prompt: str, style: str) -> str:
        keywords = {
            "realistic": "photorealistic, high resolution, professional quality",
            "cinematic": "cinematic, movie quality, dramatic lighting, film grain",
            "animated": "3D animated, Pixar-like, vibrant, polished",
            "cartoon": "cartoon style, illustrated, colorful, clean",
            "minimalist": "minimal, clean, simple, elegant",
            "dramatic": "dramatic, high contrast, bold, intense",
        }.get(style, "photorealistic, high resolution, professional quality")
        return f"{visual_prompt}. {keywords}"

    # ------------------------------------------------------------------ Billing
    async def _with_cost(self, output: dict, endpoint_id: str, model_info: dict) -> dict:
        from app.core.database import get_database
        from app.services.fal_pricing import FalPricingService

        try:
            pricing = FalPricingService(get_database())
            cost_info = await pricing.compute_cost_usd(endpoint_id)
            output["cost"] = cost_info["cost_usd"]
        except Exception as e:
            print(f"[ImageGenerator] cost calc failed: {e}")
            output["cost"] = 0.0
        output["model"] = model_info.get("name")
        output["provider"] = model_info.get("provider")
        return output
