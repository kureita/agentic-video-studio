"""Generation Pipeline - Orchestrates the full video generation workflow."""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from app.core.config import settings
from app.core.database import get_projects_collection
from app.models.project import ProjectStatus, VideoStyle, BrandProfile, Story
from app.services.scraper import WebScraper
from app.services.video_generator import VideoGenerator
from app.services.video_composer import VideoComposer
from app.agents.brand_analyzer import BrandAnalyzer
from app.agents.storyteller import Storyteller
from app.agents.script_writer import ScriptWriter


class GenerationPipeline:
    """
    Orchestrates the full video generation pipeline:
    1. Analyze - Scrape website and extract brand profile
    2. Story - Generate compelling narrative
    3. Script - Create scene-by-scene breakdown
    4. Assets - Generate video clips for each scene
    5. Compose - Combine clips (simplified for MVP)
    6. Finalize - Mark as complete
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.collection = get_projects_collection()
        
        # Initialize services
        self.scraper = WebScraper()
        self.brand_analyzer = BrandAnalyzer()
        self.storyteller = Storyteller()
        self.script_writer = ScriptWriter()
        self.video_generator = VideoGenerator()
        self.video_composer = VideoComposer()

    async def run(self):
        """Execute the full generation pipeline."""
        try:
            print(f"[Pipeline] Starting generation for project {self.project_id}")
            
            # Get project data
            project = await self._get_project()
            if not project:
                raise Exception("Project not found")

            # Stage 1: Analyze Website
            await self._update_status(ProjectStatus.ANALYZING, 5)
            brand_profile = await self._analyze_website(project)
            
            # Stage 2: Create Story
            await self._update_status(ProjectStatus.PLANNING, 20)
            story = await self._create_story(project, brand_profile)
            
            # Stage 3: Write Script
            await self._update_status(ProjectStatus.PLANNING, 35)
            scenes = await self._create_script(project, brand_profile, story)
            
            # Stage 4: Generate Video Assets
            await self._update_status(ProjectStatus.GENERATING, 50)
            scenes_with_assets = await self._generate_assets(project, scenes)
            
            # Stage 5: Compose all clips into final video using Remotion
            await self._update_status(ProjectStatus.COMPOSING, 85)
            final_video_url = await self._compose_video(
                scenes=scenes_with_assets,
                brand_profile=brand_profile,
                story=story,
            )
            
            # Stage 6: Finalize
            if final_video_url:
                await self.collection.update_one(
                    {"_id": ObjectId(self.project_id)},
                    {"$set": {"video_url": final_video_url}}
                )
            await self._update_status(ProjectStatus.COMPLETED, 100)
            print(f"[Pipeline] Completed generation for project {self.project_id}")
            
        except Exception as e:
            print(f"[Pipeline] Error in generation: {e}")
            await self._update_status(ProjectStatus.FAILED, 0, error=str(e))
            raise

    async def _get_project(self) -> Optional[dict]:
        """Get the project from database."""
        try:
            return await self.collection.find_one({"_id": ObjectId(self.project_id)})
        except Exception:
            return None

    async def _update_status(
        self, 
        status: ProjectStatus, 
        progress: int, 
        error: Optional[str] = None,
        **extra_fields
    ):
        """Update project status and progress."""
        update_data = {
            "status": status.value,
            "progress": progress,
            "updated_at": datetime.now(timezone.utc),
        }
        
        if error:
            update_data["error"] = error
        
        update_data.update(extra_fields)
        
        await self.collection.update_one(
            {"_id": ObjectId(self.project_id)},
            {"$set": update_data}
        )
        print(f"[Pipeline] Status: {status.value}, Progress: {progress}%")

    async def _analyze_website(self, project: dict) -> BrandProfile:
        """Scrape website and analyze brand."""
        website_url = project.get("website_url")
        brand_name = project.get("brand_name")
        
        print(f"[Pipeline] Analyzing website: {website_url}")
        
        # Scrape website
        scraped_content = await self.scraper.scrape(website_url)
        
        # Analyze brand
        brand_profile = await self.brand_analyzer.analyze(
            website_content=scraped_content.get("main_content", ""),
            website_url=website_url,
            brand_name=brand_name,
        )
        
        # Save brand profile to project
        await self.collection.update_one(
            {"_id": ObjectId(self.project_id)},
            {"$set": {
                "brand_profile": brand_profile.model_dump(),
                "progress": 15,
            }}
        )
        
        print(f"[Pipeline] Brand analyzed: {brand_profile.name}")
        return brand_profile

    async def _create_story(self, project: dict, brand_profile: BrandProfile) -> Story:
        """Generate story narrative."""
        print(f"[Pipeline] Creating story for {brand_profile.name}")
        
        style = VideoStyle(project.get("style", "cinematic"))
        video_duration = project.get("video_duration", 30)
        target_audience = project.get("target_audience")
        description = project.get("description")
        
        story = await self.storyteller.create_story(
            brand_profile=brand_profile,
            video_duration=video_duration,
            style=style,
            target_audience=target_audience,
            additional_notes=description,
        )
        
        # Save story to project
        await self.collection.update_one(
            {"_id": ObjectId(self.project_id)},
            {"$set": {
                "story": story.model_dump(),
                "progress": 30,
            }}
        )
        
        print(f"[Pipeline] Story created: {story.title}")
        return story

    async def _create_script(self, project: dict, brand_profile: BrandProfile, story: Story) -> list:
        """Generate scene-by-scene script."""
        print(f"[Pipeline] Writing script for {story.title}")
        
        style = VideoStyle(project.get("style", "cinematic"))
        video_duration = project.get("video_duration", 30)
        
        scenes = await self.script_writer.create_script(
            story=story,
            brand_profile=brand_profile,
            video_duration=video_duration,
            style=style,
        )
        
        # Save scenes to project
        scenes_data = [scene.model_dump() for scene in scenes]
        await self.collection.update_one(
            {"_id": ObjectId(self.project_id)},
            {"$set": {
                "scenes": scenes_data,
                "progress": 45,
            }}
        )
        
        print(f"[Pipeline] Script created with {len(scenes)} scenes")
        return scenes

    async def _generate_assets(self, project: dict, scenes: list) -> list:
        """Generate video clips for each scene and return scenes with asset URLs."""
        print(f"[Pipeline] Generating video assets for {len(scenes)} scenes")
        
        total_scenes = len(scenes)
        scenes_with_assets = []
        style = VideoStyle(project.get("style", "cinematic"))
        
        for idx, scene in enumerate(scenes):
            progress = 50 + int((idx / total_scenes) * 30)  # 50-80%
            await self._update_status(ProjectStatus.GENERATING, progress)
            
            # Build the prompt for Veo 3.1 with proper formatting
            prompt = self._build_veo_prompt(scene, style)
            
            print(f"[Pipeline] Generating scene {idx + 1}/{total_scenes}: {prompt[:100]}...")
            
            # Convert scene to dict if it's a model
            scene_dict = scene.model_dump() if hasattr(scene, 'model_dump') else dict(scene)
            
            try:
                # Generate video clip
                result = await self.video_generator.generate_clip(
                    prompt=prompt,
                    duration=8,  # Veo 3.1 max is 8 seconds
                    use_fast_model=True,  # Use fast model for MVP
                    resolution="720p",
                    aspect_ratio="16:9",
                    negative_prompt="low quality, blurry, distorted, amateur, shaky camera",
                )
                
                if result.get("success"):
                    video_url = result.get("video_url")
                    scene_dict["asset_url"] = video_url
                    
                    # Update scene in database
                    scene_id = scene_dict.get("id")
                    await self.collection.update_one(
                        {"_id": ObjectId(self.project_id), "scenes.id": scene_id},
                        {"$set": {"scenes.$.asset_url": video_url}}
                    )
                else:
                    print(f"[Pipeline] Scene {idx + 1} generation failed: {result.get('error')}")
                    
            except Exception as e:
                print(f"[Pipeline] Error generating scene {idx + 1}: {e}")
            
            scenes_with_assets.append(scene_dict)
        
        print(f"[Pipeline] Generated assets for {len(scenes_with_assets)} scenes")
        return scenes_with_assets

    async def _compose_video(
        self, 
        scenes: list, 
        brand_profile: BrandProfile, 
        story: Story
    ) -> Optional[str]:
        """Compose all scene videos into a final video using Remotion."""
        if not scenes:
            print("[Pipeline] No scenes to compose")
            return None
        
        # Check if any scenes have assets
        scenes_with_video = [s for s in scenes if s.get("asset_url")]
        if not scenes_with_video:
            print("[Pipeline] No scenes have video assets")
            return None
        
        print(f"[Pipeline] Composing {len(scenes_with_video)} scenes with Remotion...")
        
        final_url = await self.video_composer.compose_video(
            project_id=self.project_id,
            scenes=scenes,
            brand_profile=brand_profile.model_dump() if hasattr(brand_profile, 'model_dump') else dict(brand_profile),
            story=story.model_dump() if hasattr(story, 'model_dump') else dict(story),
        )
        
        if final_url:
            print(f"[Pipeline] Final video: {final_url}")
        else:
            print("[Pipeline] Composition failed, using first clip")
            final_url = scenes_with_video[0].get("asset_url") if scenes_with_video else None
        
        return final_url

    def _build_veo_prompt(self, scene, style: VideoStyle) -> str:
        """
        Build a well-structured prompt for Veo 3.1 following the prompt guide.
        
        Veo prompts should include:
        - Subject: The main focus
        - Action: What's happening
        - Style: Visual aesthetic
        - Camera: Positioning and motion
        - Composition: Shot framing
        - Ambiance: Lighting and mood
        - Audio cues: Dialogue, SFX, ambient sounds
        """
        visual_prompt = scene.visual_prompt if hasattr(scene, 'visual_prompt') else scene.get("visual_prompt", "")
        voiceover = scene.voiceover_text if hasattr(scene, 'voiceover_text') else scene.get("voiceover_text")
        
        # Map style to Veo-friendly style keywords
        style_keywords = {
            VideoStyle.CINEMATIC: "cinematic, professional lighting, high production value",
            VideoStyle.MINIMAL: "clean, minimalist, subtle movements, elegant simplicity",
            VideoStyle.ENERGETIC: "dynamic, fast-paced, vibrant colors, high energy",
            VideoStyle.ELEGANT: "sophisticated, refined, smooth transitions, premium feel",
            VideoStyle.PLAYFUL: "fun, colorful, animated style, whimsical",
            VideoStyle.CORPORATE: "clean, professional, modern corporate style",
        }
        
        style_desc = style_keywords.get(style, "cinematic, high quality")
        
        # Build the comprehensive prompt
        prompt_parts = [
            f"{style_desc}.",
            visual_prompt,
        ]
        
        # Add dialogue/narration for Veo 3's native audio generation
        if voiceover:
            # Format dialogue properly for Veo
            prompt_parts.append(f'Narrator speaks: "{voiceover}"')
        
        return " ".join(prompt_parts)


async def run_generation_pipeline(project_id: str):
    """
    Background task to run the generation pipeline.
    Called from the /start endpoint.
    """
    pipeline = GenerationPipeline(project_id)
    await pipeline.run()

