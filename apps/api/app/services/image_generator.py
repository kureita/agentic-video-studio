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

from app.core.model_registry import get_model_by_name
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
        
        # Determine the target model
        target_model = self.default_model
        if model_name:
            model_info = get_model_by_name(model_name)
            if model_info and "air_id" in model_info:
                target_model = model_info["air_id"]
            else:
                # Pass through literally if it looks like an AIR ID (has ':'), else fallback
                target_model = model_name if ":" in model_name else self.default_model
                
        try:
            # Map aspect ratio to valid Runware dimensions
            # For Kling and Seedream, they strictly enforce exact predefined dimensions that are NOT multiples of 64
            is_strict_model = "kling" in target_model.lower() or "seedream" in target_model.lower()
            
            if is_strict_model:
                dimensions = {
                    "16:9": (1360, 768),
                    "9:16": (768, 1360),
                    "1:1":  (1024, 1024),
                    "4:3":  (1168, 880),
                    "3:4":  (880, 1168),
                    "3:2":  (1248, 832),
                    "2:3":  (832, 1248),
                    "21:9": (1552, 656)
                }
            else:
                # Standard models (FLUX) require dimensions to be strict multiples of 64
                dimensions = {
                    "16:9": (1280, 768),
                    "9:16": (768, 1280),
                    "1:1":  (1024, 1024),
                    "4:3":  (1024, 768),
                    "3:4":  (768, 1024),
                    "3:2":  (1152, 768),
                    "2:3":  (768, 1152),
                    "21:9": (1536, 640)
                }
                
            width, height = dimensions.get(aspect_ratio, (1024, 1024))
            
            # Enhance prompt with style
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
            
            print(f"[ImageGenerator] Generating image with {target_model}: {enhanced_prompt[:100]}...")
            
            # Use image-to-image or text-to-image
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
