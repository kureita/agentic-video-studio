"""Image Generator Service - Uses Gemini for image generation."""

import asyncio
import os
import random
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from app.core.config import settings


class ImageGenerator:
    """Generates images using Gemini (Nano Banana) for consistent scene visuals."""

    def __init__(self):
        self.use_mock = settings.use_mock_veo  # Use same mock flag for development
        
        # Ensure output directory exists
        self.output_dir = Path("static/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
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
        images = list(self.output_dir.glob("*.png")) + list(self.output_dir.glob("*.jpg"))
        if images:
            return random.choice(images)
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
            filename = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
            # For mock, just return a placeholder URL pointing to a sample image
            image_url = f"{settings.api_base_url}/static/images/{mock_source.name}"
            print(f"[ImageGenerator] MOCK: Generated (using {mock_source.name}): {image_url}")
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

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        style: str = "realistic",
    ) -> dict:
        """
        Generate an image from a text prompt using Gemini.
        
        Args:
            prompt: Detailed description of the image to generate
            aspect_ratio: Aspect ratio (16:9, 9:16, 1:1, etc.)
            style: Visual style (realistic, cinematic, animated, etc.)
            
        Returns:
            Dictionary with image URL and metadata
        """
        # Use mock mode if enabled
        if self.use_mock:
            return await self._mock_generate(prompt)
        
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
            
            print(f"[ImageGenerator] Generating image: {enhanced_prompt[:100]}...")
            
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
                model=self.model,
                contents=[enhanced_prompt],
                config=config,
            )
            
            # Extract image from response
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    # Save the image
                    filename = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
                    image_path = self.output_dir / filename
                    
                    # Save image data
                    with open(image_path, "wb") as f:
                        f.write(part.inline_data.data)
                    
                    image_url = f"{settings.api_base_url}/static/images/{filename}"
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

