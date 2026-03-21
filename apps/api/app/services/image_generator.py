"""Image Generator Service - Uses Runware API for all image generation."""

import asyncio
import os
import random
import time
from pathlib import Path
from typing import Optional
import httpx

from app.core.config import settings
from app.core.dependencies import get_storage_service
from app.services.runware_service import RunwareService

from app.core.model_registry import resolve_air_id, get_model_by_id, get_model_by_name
class ImageGenerator:
    """Generates images using Runware API (Flux, Recraft, Kling, etc) for consistent scene visuals."""

    def __init__(self):
        self.use_mock = settings.use_mock_veo  # Keep using the same mock flag for dev
        self.storage = get_storage_service()
        self.runware = RunwareService()
        
        if self.use_mock:
            print("[ImageGenerator] Running in MOCK mode - no API calls will be made")
        else:
            print("[ImageGenerator] Running in PRODUCTION mode - using Runware API")
        
        # Default model for general text-to-image
        self.default_model = "bfl:flux-2@dev"  # FLUX.2 [dev] — cheapest image model in registry

    def _get_mock_image(self) -> Optional[Path]:
        """Get a random existing image from static/images for mock mode."""
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
        """Mock image generation - simulates delay and returns placeholder."""
        print(f"[ImageGenerator] MOCK: Simulating generation for prompt: {prompt[:80]}...")
        
        delay = random.uniform(2, 5)
        await asyncio.sleep(delay)
        
        mock_source = self._get_mock_image()
        
        if mock_source:
             try:
                 with open(mock_source, "rb") as f:
                     content = f.read()
                 filename = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
                 image_url = await self.storage.upload_file(content, filename, "image/png")
                 print(f"[ImageGenerator] MOCK: Generated (uploaded mock): {image_url}")
             except Exception as e:
                 print(f"[ImageGenerator] Mock upload failed: {e}")
                 image_url = f"{settings.api_base_url}/static/images/{mock_source.name}"
        else:
            image_url = f"https://picsum.photos/seed/{int(time.time())}/1344/768"
            print(f"[ImageGenerator] MOCK: Generated placeholder: {image_url}")
        
        return {
            "success": True,
            "image_url": image_url,
            "prompt": prompt,
            "mock": True,
        }

    async def _fetch_image(self, url: str) -> Optional[bytes]:
        """Fetch image bytes from URL or decode from data URL."""
        if not url:
            return None
        try:
            if url.startswith('data:'):
                import base64
                if ';base64,' in url:
                    base64_data = url.split(';base64,')[1]
                    image_bytes = base64.b64decode(base64_data)
                    return image_bytes
                return None
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                if response.status_code == 200:
                    return response.content
        except Exception as e:
            print(f"[ImageGenerator] Error fetching image {url[:100]}...: {e}")
        return None

    def _check_model_i2i_support(self, model_name: Optional[str]) -> tuple:
        """Check if a model supports image-to-image (reference images).

        Returns (supports_i2i: bool, model_display_name: str).

        ┌──────────────────────────────────────────────────────────────────┐
        │  REFERENCE IMAGE SUPPORT BY MODEL (as of March 2026)            │
        │                                                                  │
        │  Model                  i2i?   Mechanism      Max refs           │
        │  ─────────────────────  ─────  ─────────────  ────────           │
        │  GPT Image 1            ✅     referenceImages  1+               │
        │  DALL-E 3               ❌     —               —                 │
        │  FLUX.2 [max]           ✅     seedImage        1                │
        │  Nano Banana 2          ✅     referenceImages  1+               │
        │  Kling IMAGE O3         ✅     referenceImages  1+               │
        │  Seedream 5.0 Lite      ❌     —               —                 │
        │  Recraft V4             ✅     referenceImages  1 (inconsistent) │
        │  Recraft V4 Pro         ✅     referenceImages  1 (inconsistent) │
        │  Grok Imagine Image     ❌     —               —                 │
        │  Imagen 4 Ultra         ❌     —               —                 │
        │  Imagen 4 Preview       ❌     —               —                 │
        │  FLUX.2 [dev]           ✅     seedImage        1                │
        │  FLUX.2 [flex]          ✅     seedImage        1                │
        │  FLUX.2 [klein] 9B      ❌     —               —                 │
        │                                                                  │
        │  ⚠️ If a model says ❌ and the user connected a ref image,      │
        │  we must REJECT the request with a clear error — not silently    │
        │  send a payload that Runware will 400 on.                        │
        └──────────────────────────────────────────────────────────────────┘
        """
        if not model_name:
            return True, "Unknown"

        entry = get_model_by_id(model_name) or get_model_by_name(model_name)
        if not entry:
            return True, model_name

        capabilities = [c.lower() for c in entry.get("capabilities", [])]
        display_name = entry.get("name", model_name)
        return "i2i" in capabilities, display_name

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        style: str = "realistic",
        reference_image: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict:
        """
        Generate an image from a text prompt using Runware.
        """
        if self.use_mock:
            return await self._mock_generate(prompt)
        
        # Determine the target model — always resolve to a valid AIR ID
        target_model = resolve_air_id(model_name, self.default_model, model_type="image")

        # ── Validate ref image support BEFORE calling Runware ──
        # This prevents cryptic Runware 400 errors when the user connects
        # a reference image to a model that doesn't support i2i.
        if reference_image:
            supports_i2i, display_name = self._check_model_i2i_support(model_name)
            if not supports_i2i:
                return {
                    "success": False,
                    "error": (
                        f"'{display_name}' does not support reference images (image-to-image). "
                        f"Either disconnect the reference image, or switch to a model that supports it "
                        f"(look for 'Text to Image & Image to Image' in the model selector)."
                    ),
                }
                
        try:
            width, height = self.runware._resolve_image_dimensions(target_model, aspect_ratio)
            
            style_prompts = {
                "realistic": "photorealistic, high detail, professional photography",
                "cinematic": "cinematic lighting, movie still, dramatic composition",
                "animated": "3D animation style, Pixar quality, vibrant colors",
                "cartoon": "illustrated style, colorful cartoon, clean lines",
                "minimalist": "minimal design, clean aesthetic, simple composition",
                "dramatic": "high contrast, bold lighting, intense atmosphere",
            }
            
            style_suffix = style_prompts.get(style, style_prompts["realistic"])
            enhanced_prompt = f"{prompt}. {style_suffix}"
            
            print(f"[ImageGenerator] Generating image with {target_model} ({width}x{height}): {enhanced_prompt[:100]}...")
            
            if reference_image:
                print(f"[ImageGenerator] Processing reference image: {reference_image[:80]}...")
                enhanced_prompt = f"Based on the provided reference image: {enhanced_prompt}"
                result = await self.runware.image_to_image(
                    prompt=enhanced_prompt,
                    image_url=reference_image,
                    width=width,
                    height=height,
                    model=target_model
                )
            else:
                result = await self.runware.generate_image(
                    prompt=enhanced_prompt,
                    width=width,
                    height=height,
                    model=target_model
                )
            
            # Make sure we store the image locally/S3 if we want persistence
            if result.get("success"):
                image_url = result.get("image_url")
                # Runware provides URLs that expire or we might want them in our S3
                img_bytes = await self._fetch_image(image_url)
                if img_bytes:
                    filename = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
                    final_url = await self.storage.upload_file(img_bytes, filename, "image/png")
                    result["image_url"] = final_url
                    print(f"[ImageGenerator] Image saved to storage: {final_url}")
            
            return result
            
        except Exception as e:
            print(f"[ImageGenerator] Error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def generate_scene_images(
        self,
        scenes: list,
        visual_style: str = "realistic",
        aspect_ratio: str = "16:9",
    ) -> list:
        """Generate images for multiple scenes."""
        results = []
        total = len(scenes)
        
        for idx, scene in enumerate(scenes):
            print(f"[ImageGenerator] Generating image {idx + 1}/{total}...")
            visual_prompt = scene.get("visual_prompt", "") or scene.get("description", "")
            image_prompt = self._build_image_prompt(visual_prompt, visual_style)
            
            result = await self.generate_image(
                prompt=image_prompt,
                aspect_ratio=aspect_ratio,
                style=visual_style,
            )
            
            scene_result = dict(scene)
            scene_result["image_prompt"] = image_prompt
            
            if result.get("success"):
                scene_result["image_url"] = result.get("image_url")
            
            results.append(scene_result)
        
        return results

    def _build_image_prompt(self, visual_prompt: str, style: str) -> str:
        """Build a comprehensive image generation prompt."""
        style_keywords = {
            "realistic": "photorealistic, high resolution, professional quality",
            "cinematic": "cinematic, movie quality, dramatic lighting, film grain",
            "animated": "3D animated, Pixar-like, vibrant, polished",
            "cartoon": "cartoon style, illustrated, colorful, clean",
            "minimalist": "minimal, clean, simple, elegant",
            "dramatic": "dramatic, high contrast, bold, intense",
        }
        
        keywords = style_keywords.get(style, style_keywords["realistic"])
        return f"{visual_prompt}. {keywords}"
