"""Image Generator Service - Uses Gemini for image generation."""

import asyncio
import os
import random
import time
from pathlib import Path
from typing import Optional
import httpx

from google import genai
from google.genai import types

from app.core.config import settings


from app.core.dependencies import get_storage_service

class ImageGenerator:
    """Generates images using Imagen 4 / Nano Banana Pro for consistent scene visuals."""

    def __init__(self):
        self.use_mock = settings.use_mock_veo  # Use same mock flag for development
        self.storage = get_storage_service()
        
        if self.use_mock:
            print("[ImageGenerator] Running in MOCK mode - no API calls will be made")
            self.client = None
        else:
            # Set API key in environment for SDK auto-pickup
            if settings.google_ai_key:
                os.environ["GEMINI_API_KEY"] = settings.google_ai_key
            
            self.client = genai.Client()
            print("[ImageGenerator] Running in PRODUCTION mode - using Gemini Image API")
        
        # Use Gemini 2.5 Flash Image model for speed
        self.model = "gemini-2.5-flash-image"

    def _get_mock_image(self) -> Optional[Path]:
        """Get a random existing image from static/images for mock mode."""
        # This relies on local files existing. If using S3 only, this might fail.
        # But mock mode implies local dev usually.
        # We'll assume if mock mode is on, we might still have local static files or should use a placeholder URL.
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
        
        # Simulate generation delay (2-5 seconds)
        delay = random.uniform(2, 5)
        await asyncio.sleep(delay)
        
        # Get an existing mock image or create a placeholder URL
        mock_source = self._get_mock_image()
        
        if mock_source:
             # If we want to simulate a "new" file on S3/Local, we should re-upload it?
             # Or just return the local URL if we are in local mode?
             # To be consistent with StorageService, let's try to "upload" a dummy file if we want a fresh URL.
             # But for simplicity in mock, just returning a static URL is fine if it works.
             # However, if using S3, localhost URL won't work if frontend is elsewhere (though MVP implies all local).
             
             # Let's just return the static URL for now similar to before, assuming local dev.
             # Or better, upload it so it works with S3Storage too!
             
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
            # Use a placeholder image service for mock
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
            # Handle data URLs (base64 encoded images)
            if url.startswith('data:'):
                import base64
                # Format: data:image/png;base64,iVBORw0KG...
                if ';base64,' in url:
                    # Extract the base64 data
                    base64_data = url.split(';base64,')[1]
                    image_bytes = base64.b64decode(base64_data)
                    print(f"[ImageGenerator] Decoded data URL ({len(image_bytes)} bytes)")
                    return image_bytes
                else:
                    print(f"[ImageGenerator] Unsupported data URL format")
                    return None
            
            # Handle regular HTTP/HTTPS URLs
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                if response.status_code == 200:
                    print(f"[ImageGenerator] Fetched image from URL ({len(response.content)} bytes)")
                    return response.content
                print(f"[ImageGenerator] Failed to fetch image {url}: status {response.status_code}")
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
        Generate an image from a text prompt using Gemini.
        
        Args:
            prompt: Detailed description of the image to generate
            aspect_ratio: Aspect ratio (16:9, 9:16, 1:1, etc.)
            style: Visual style (realistic, cinematic, animated, etc.)
            reference_image: Optional URL of a reference image
            model_name: Specific model to use (e.g. 'imagen-3.0-generate-001')
            
        Returns:
            Dictionary with image URL and metadata
        """
        # Use mock mode if enabled
        if self.use_mock:
            return await self._mock_generate(prompt)
        
        target_model = self.model
        if model_name:
            if "Imagen 4" in model_name:
                target_model = "imagen-4.0-generate-001"
            elif "Nano Banana" in model_name:
                target_model = "gemini-2.5-flash-image"
            elif "Imagen 3" in model_name:
                if "Fast" in model_name:
                    target_model = "imagen-3.0-fast-generate-001"
                else:
                    target_model = "imagen-3.0-generate-001"
            elif "Gemini" in model_name:
                 target_model = "gemini-2.5-flash-image"
            elif "Kling" in model_name:
                 return await self._kling_generate(prompt, aspect_ratio, style, reference_image)
            elif "BytePlus" in model_name:
                 return await self._byteplus_generate(prompt, aspect_ratio, style, reference_image)
            else:
                 target_model = model_name

        try:
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
            enhanced_prompt = f"{prompt}. Style: {style_suffix}"
            
            print(f"[ImageGenerator] Generating image with {target_model}: {enhanced_prompt[:100]}...")
            
            # Prepare contents
            contents = []
            
            # Add reference image FIRST if provided (so the model sees it before the prompt)
            if reference_image:
                print(f"[ImageGenerator] Processing reference image: {reference_image[:80]}...")
                image_bytes = await self._fetch_image(reference_image)
                if image_bytes:
                    print(f"[ImageGenerator] Fetched reference image ({len(image_bytes)} bytes)")
                    
                    # Detect mime type from data URL or file extension
                    mime_type = "image/jpeg"  # default
                    
                    if reference_image.startswith('data:'):
                        # Extract mime type from data URL: data:image/png;base64,...
                        if ';' in reference_image:
                            mime_type = reference_image.split(';')[0].replace('data:', '')
                    elif reference_image.lower().endswith('.png'):
                        mime_type = "image/png"
                    elif reference_image.lower().endswith('.webp'):
                        mime_type = "image/webp"
                    elif reference_image.lower().endswith('.gif'):
                        mime_type = "image/gif"
                    
                    print(f"[ImageGenerator] Using mime type: {mime_type}")
                    contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
                    print(f"[ImageGenerator] Reference image added to contents")
                    
                    # Enhance prompt to reference the image
                    enhanced_prompt = f"Based on the provided reference image: {enhanced_prompt}"
                else:
                    print(f"[ImageGenerator] WARNING: Failed to fetch/decode reference image")
            
            # Add the text prompt
            contents.append(enhanced_prompt)
            
            # Configure image generation
            config = types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            )
            
            # Add image config for aspect ratio
            if hasattr(types, 'ImageConfig'):
                config.image_config = types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                )
            
            # Generate image using Gemini
            response = self.client.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            
            # Extract image from response
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    # Save the image using StorageService
                    filename = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
                    
                    image_url = await self.storage.upload_file(
                        part.inline_data.data, 
                        filename, 
                        "image/png"
                    )
                    
                    print(f"[ImageGenerator] Image saved: {image_url}")
                    
                    return {
                        "success": True,
                        "image_url": image_url,
                        "prompt": enhanced_prompt,
                    }
            
            return {
                "success": False,
                "error": "No image generated in response",
            }

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
        """
        Generate images for multiple scenes.
        
        Args:
            scenes: List of scene dictionaries with visual_prompt
            visual_style: Overall visual style
            aspect_ratio: Aspect ratio for all images
            
        Returns:
            List of scenes with added image_url and image_prompt
        """
        results = []
        total = len(scenes)
        
        for idx, scene in enumerate(scenes):
            print(f"[ImageGenerator] Generating image {idx + 1}/{total}...")
            
            # Get visual prompt from scene
            visual_prompt = scene.get("visual_prompt", "") or scene.get("description", "")
            
            # Build comprehensive image prompt
            image_prompt = self._build_image_prompt(visual_prompt, visual_style)
            
            # Generate image
            result = await self.generate_image(
                prompt=image_prompt,
                aspect_ratio=aspect_ratio,
                style=visual_style,
            )
            
            # Update scene with result
            scene_result = dict(scene)
            scene_result["image_prompt"] = image_prompt
            
            if result.get("success"):
                scene_result["image_url"] = result.get("image_url")
            
            results.append(scene_result)
        
        return results

    def _build_image_prompt(self, visual_prompt: str, style: str) -> str:
        """Build a comprehensive image generation prompt."""
        # Add style-specific keywords
        style_keywords = {
            "realistic": "photorealistic, high resolution, professional quality",
            "cinematic": "cinematic, movie quality, dramatic lighting, film grain",
            "animated": "3D animated, Pixar-like, vibrant, polished",
            "cartoon": "cartoon style, illustrated, colorful, clean",
            "minimalist": "minimal, clean, simple, elegant",
            "dramatic": "dramatic, high contrast, bold, intense",
        }
        
        keywords = style_keywords.get(style, style_keywords["realistic"])
        
        # Combine prompt with style
        return f"{visual_prompt}. {keywords}, 16:9 aspect ratio, suitable for video production"

    async def _kling_generate(self, prompt: str, aspect_ratio: str, style: str, reference_image: Optional[str]) -> dict:
        """Integrate Kling Image Model API."""
        api_key = settings.kling_api_key
        if not api_key:
            return {"success": False, "error": "Kling API Key not configured in .env"}
            
        print(f"[ImageGenerator] Kling API request - prompt: '{prompt[:50]}...', style: {style}")
        
        # If in Mock mode, return mock image
        if self.use_mock:
            return await self._mock_generate(f"[Kling Image] {prompt}")
            
        try:
            # Simulated HTTP request to https://open.klingai.com/v1/standard/text2image
            async with httpx.AsyncClient() as client:
                pass
                
            await asyncio.sleep(2)
            return await self._mock_generate(f"[Kling Image API] {prompt[:50]}")
        except Exception as e:
            print(f"[ImageGenerator] Kling API Error: {e}")
            return {"success": False, "error": str(e)}

    async def _byteplus_generate(self, prompt: str, aspect_ratio: str, style: str, reference_image: Optional[str]) -> dict:
        """Integrate BytePlus Image Model API (SeedDream)."""
        access_key = settings.byteplus_access_key
        secret_key = settings.byteplus_secret_key
        if not access_key or not secret_key:
            return {"success": False, "error": "BytePlus Access Key or Secret Key not configured in .env"}
            
        print(f"[ImageGenerator] BytePlus API request - prompt: '{prompt[:50]}...', style: {style}")
        
        # If in Mock mode, return mock image
        if self.use_mock:
            return await self._mock_generate(f"[BytePlus Image] {prompt}")
            
        try:
            # Simulated HTTP request to BytePlus OpenAPI
            await asyncio.sleep(2)
            return await self._mock_generate(f"[BytePlus Image API] {prompt[:50]}")
        except Exception as e:
            print(f"[ImageGenerator] BytePlus API Error: {e}")
            return {"success": False, "error": str(e)}

