"""Canvas Pipeline Endpoints - Step-by-step video generation with user control."""

from datetime import datetime, timezone
from typing import Optional, List
import os

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.core.database import get_projects_collection
from app.models.project import ProjectStatus, VideoStyle, BrandProfile, Story, Scene
from app.services.scraper import WebScraper
from app.services.llm import get_llm
from app.services.image_generator import ImageGenerator
from app.services.video_generator import VideoGenerator
from app.services.video_composer import VideoComposer
from app.agents.brand_analyzer import BrandAnalyzer
from app.agents.storyteller import Storyteller
from app.agents.script_writer import ScriptWriter
from app.services.frame_extractor import FrameExtractor

router = APIRouter(prefix="/canvas", tags=["canvas"])


# ============================================
# Request/Response Models
# ============================================

class CanvasCreateRequest(BaseModel):
    website_url: HttpUrl


class CanvasCreateResponse(BaseModel):
    project_id: str
    brand_profile: dict


class StoryOptionsRequest(BaseModel):
    theme: str = "modern"
    visual_style: str = "realistic"
    direction: str = "inspirational"
    duration: int = 30
    target_audience: Optional[str] = None
    additional_notes: Optional[str] = None


class StoryResponse(BaseModel):
    story: dict
    scenes: List[dict]


class ImproveStoryRequest(BaseModel):
    synopsis: str
    script_text: str


class ImageGenerateRequest(BaseModel):
    visual_style: str = "realistic"


class ImageRegenerateRequest(BaseModel):
    prompt: Optional[str] = None
    visual_style: str = "realistic"


class ImagePromptItem(BaseModel):
    scene_id: int
    visual_prompt: str


class ImproveImagePromptsRequest(BaseModel):
    prompts: List[ImagePromptItem]
    visual_style: str = "realistic"


class ImproveImagePromptsResponse(BaseModel):
    prompts: List[ImagePromptItem]


class ImageResponse(BaseModel):
    scenes: List[dict]


class SingleImageResponse(BaseModel):
    image_url: str
    image_prompt: str


class VideoResponse(BaseModel):
    scenes: List[dict]



class VideoRegenerateRequest(BaseModel):
    prompt: Optional[str] = None
    image_url: Optional[str] = None


class SingleVideoResponse(BaseModel):
    video_url: str


class ComposeRequest(BaseModel):
    transition: str = "fade"
    show_brand_watermark: bool = True
    show_cta: bool = True


class ComposeResponse(BaseModel):
    preview_url: str


class RenderRequest(BaseModel):
    resolution: str = "1080p"


class RenderResponse(BaseModel):
    video_url: str


class ExtractFrameRequest(BaseModel):
    video_url: str
    num_frames: int = 1


class ExtractFrameResponse(BaseModel):
    frame_url: str


class CanvasStateRequest(BaseModel):
    """Save the canvas flow state (nodes and edges)."""
    nodes: List[dict]
    edges: List[dict]


class CanvasStateResponse(BaseModel):
    nodes: List[dict]
    edges: List[dict]
    

class ProjectLoadResponse(BaseModel):
    project_id: str
    brand_profile: Optional[dict] = None
    story: Optional[dict] = None
    scenes: List[dict] = []
    story_options: Optional[dict] = None
    canvas_state: Optional[dict] = None
    status: str
    progress: int


# ============================================
# Endpoints
# ============================================

@router.get("/{project_id}", response_model=ProjectLoadResponse)
async def load_canvas_project(project_id: str):
    """Load an existing canvas project with all its data."""
    collection = get_projects_collection()
    
    try:
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return ProjectLoadResponse(
            project_id=str(project["_id"]),
            brand_profile=project.get("brand_profile"),
            story=project.get("story"),
            scenes=project.get("scenes", []),
            story_options=project.get("story_options"),
            canvas_state=project.get("canvas_state"),
            status=project.get("status", "draft"),
            progress=project.get("progress", 0),
        )
    except Exception as e:
        print(f"[Canvas] Error loading project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}/state", response_model=CanvasStateResponse)
async def save_canvas_state(project_id: str, request: CanvasStateRequest):
    """Save the canvas flow state (nodes and edges positions)."""
    collection = get_projects_collection()
    
    try:
        result = await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "canvas_state": {
                    "nodes": request.nodes,
                    "edges": request.edges,
                },
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return CanvasStateResponse(
            nodes=request.nodes,
            edges=request.edges,
        )
    except Exception as e:
        print(f"[Canvas] Error saving state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=CanvasCreateResponse)
async def create_canvas_project(request: CanvasCreateRequest):
    """Create a new canvas project and analyze the website/brand."""
    collection = get_projects_collection()
    scraper = WebScraper()
    brand_analyzer = BrandAnalyzer()
    
    try:
        # Create project document
        project_data = {
            "website_url": str(request.website_url),
            "status": ProjectStatus.ANALYZING.value,
            "progress": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "pipeline_type": "canvas",  # Mark as canvas pipeline
        }
        
        result = await collection.insert_one(project_data)
        project_id = str(result.inserted_id)
        
        print(f"[Canvas] Created project {project_id}, analyzing website...")
        
        # Scrape and analyze website
        scraped_content = await scraper.scrape(str(request.website_url))
        
        brand_profile = await brand_analyzer.analyze(
            website_content=scraped_content.get("main_content", ""),
            website_url=str(request.website_url),
            brand_name=None,
        )
        
        # Update project with brand profile
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "brand_profile": brand_profile.model_dump(),
                "brand_name": brand_profile.name,
                "status": ProjectStatus.PLANNING.value,
                "progress": 20,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        print(f"[Canvas] Brand analyzed: {brand_profile.name}")
        
        return CanvasCreateResponse(
            project_id=project_id,
            brand_profile=brand_profile.model_dump(),
        )
        
    except Exception as e:
        print(f"[Canvas] Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/story", response_model=StoryResponse)
async def generate_story(project_id: str, request: StoryOptionsRequest):
    """Generate story and script based on options."""
    collection = get_projects_collection()
    storyteller = Storyteller()
    script_writer = ScriptWriter()
    
    try:
        # Get project
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        brand_profile_data = project.get("brand_profile")
        if not brand_profile_data:
            raise HTTPException(status_code=400, detail="Brand profile not available")
        
        brand_profile = BrandProfile(**brand_profile_data)
        
        # Map visual style to VideoStyle
        style_mapping = {
            "realistic": VideoStyle.CINEMATIC,
            "cinematic": VideoStyle.CINEMATIC,
            "animated": VideoStyle.PLAYFUL,
            "cartoon": VideoStyle.PLAYFUL,
            "minimalist": VideoStyle.MINIMAL,
            "dramatic": VideoStyle.ELEGANT,
        }
        video_style = style_mapping.get(request.visual_style, VideoStyle.CINEMATIC)
        
        print(f"[Canvas] Generating story for {brand_profile.name}...")
        
        # Generate story
        story = await storyteller.create_story(
            brand_profile=brand_profile,
            video_duration=request.duration,
            style=video_style,
            target_audience=request.target_audience,
            additional_notes=f"Theme: {request.theme}. Direction: {request.direction}. {request.additional_notes or ''}",
        )
        
        print(f"[Canvas] Story created: {story.title}")
        
        # Generate script
        scenes = await script_writer.create_script(
            story=story,
            brand_profile=brand_profile,
            video_duration=request.duration,
            style=video_style,
            additional_context=request.additional_notes,
        )
        
        print(f"[Canvas] Script created with {len(scenes)} scenes")
        
        # Save to project
        scenes_data = [scene.model_dump() for scene in scenes]
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "story": story.model_dump(),
                "scenes": scenes_data,
                "story_options": request.model_dump(),
                "video_duration": request.duration,
                "style": video_style.value,
                "progress": 40,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        return StoryResponse(
            story=story.model_dump(),
            scenes=scenes_data,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error generating story: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/story/improve", response_model=StoryResponse)
async def improve_story(project_id: str, request: ImproveStoryRequest):
    """Improve/edit story and script using LLM - enhances writing quality."""
    collection = get_projects_collection()
    llm = get_llm("openai")
    
    try:
        # Get project
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        current_story = project.get("story", {})
        brand_profile = project.get("brand_profile", {})
        story_options = project.get("story_options", {})
        
        print(f"[Canvas] Improving story for project {project_id}...")
        
        # Use LLM to improve the content
        system_prompt = """You are an expert video scriptwriter and storyteller. Your task is to IMPROVE the given story and script content to make it more:

1. Engaging and emotionally compelling
2. Clear and concise - every word should count
3. Visually descriptive for video generation
4. Professionally written with proper flow and pacing
5. Aligned with the brand's voice and messaging

IMPORTANT: 
- Keep the original intent and message but enhance the quality
- Make visual prompts more detailed and cinematic
- Ensure smooth transitions between scenes
- Preserve the scene structure (IDs, timing) but improve descriptions
        
Return JSON with:
{
    "story": {
        "title": "Improved title",
        "synopsis": "Enhanced synopsis - more engaging and impactful",
        "key_messages": ["key message 1", "key message 2"],
        "target_emotion": "primary emotion to evoke",
        "call_to_action": "Strong call to action"
    },
    "scenes": [
        {
            "id": 1,
            "start_time": 0,
            "end_time": 8,
            "description": "Improved scene description",
            "visual_prompt": "Detailed, cinematic visual description for AI video generation. Include camera angles, lighting, mood, and specific visual elements.",
            "voiceover_text": "Improved voiceover narration or null",
            "on_screen_text": "Text overlay or null"
        }
    ]
}"""
        
        user_prompt = f"""Please improve this video script content:

**Brand:** {brand_profile.get('name', 'Brand')}
**Brand Description:** {brand_profile.get('description', '')}
**Tone:** {brand_profile.get('tone', 'professional')}
**Visual Style:** {story_options.get('visual_style', 'cinematic')}
**Direction:** {story_options.get('direction', 'inspirational')}

**Current Story Title:** {current_story.get('title', 'Untitled')}

**Synopsis to Improve:**
{request.synopsis}

**Script/Scenes to Improve:**
{request.script_text}

Enhance this content while keeping the same structure and timing. Make it more professional, engaging, and visually compelling for video generation."""

        result = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            json_response=True,
        )
        
        import json
        parsed = json.loads(result)
        
        story_data = parsed.get("story", current_story)
        scenes_data = parsed.get("scenes", [])
        
        # Preserve scene timing from original if not in response
        original_scenes = project.get("scenes", [])
        for i, scene in enumerate(scenes_data):
            if i < len(original_scenes):
                if "start_time" not in scene:
                    scene["start_time"] = original_scenes[i].get("start_time", i * 8)
                if "end_time" not in scene:
                    scene["end_time"] = original_scenes[i].get("end_time", (i + 1) * 8)
        
        # Update project with improved content
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "story": story_data,
                "scenes": scenes_data,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        print(f"[Canvas] Story improved successfully")
        
        return StoryResponse(
            story=story_data,
            scenes=scenes_data,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error improving story: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/images/improve", response_model=ImproveImagePromptsResponse)
async def improve_image_prompts(project_id: str, request: ImproveImagePromptsRequest):
    """Improve image generation prompts using LLM for better visual output."""
    collection = get_projects_collection()
    llm = get_llm("openai")
    
    try:
        # Get project for context
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        brand_profile = project.get("brand_profile", {})
        story = project.get("story", {})
        
        print(f"[Canvas] Improving {len(request.prompts)} image prompts...")
        
        # Build prompts text
        prompts_text = "\n".join([
            f"Scene {p.scene_id}: {p.visual_prompt}"
            for p in request.prompts
        ])
        
        system_prompt = """You are an expert at writing image generation prompts for AI systems like Gemini Imagen.
Your task is to improve the given visual prompts to produce better, more consistent, and more visually appealing images.

For each prompt, enhance it by:
1. MANDATORY: Include the Brand Name and relevant product details.
2. Specify the narrative purpose of this shot (e.g., "illustrating growth").
3. Add specific visual details (lighting, camera angle, composition).
4. Include style descriptors that match the visual style.
5. Add atmosphere and mood elements.
6. Ensure consistency across scenes (similar visual language).

The result must be a highly detailed, brand-aware prompt ready for a top-tier image generator.

Return JSON:
{
    "prompts": [
        {"scene_id": 1, "visual_prompt": "Highly detailed brand-specific prompt..."},
        {"scene_id": 2, "visual_prompt": "..."}
    ]
}"""

        user_prompt = f"""Improve these image generation prompts:

**Brand:** {brand_profile.get('name', 'Brand')}
**Story:** {story.get('title', 'Video')}
**Visual Style:** {request.visual_style}

**Current Prompts:**
{prompts_text}

Enhance each prompt for better AI image generation. Keep scene IDs the same."""

        result = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            json_response=True,
        )
        
        import json
        parsed = json.loads(result)
        
        improved_prompts = parsed.get("prompts", [])
        
        # Update scenes in project with improved prompts
        scenes = project.get("scenes", [])
        for improved in improved_prompts:
            scene_id = improved.get("scene_id")
            new_prompt = improved.get("visual_prompt")
            for scene in scenes:
                if scene.get("id") == scene_id:
                    scene["visual_prompt"] = new_prompt
                    break
        
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "scenes": scenes,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        print(f"[Canvas] Image prompts improved successfully")
        
        return ImproveImagePromptsResponse(
            prompts=[ImagePromptItem(**p) for p in improved_prompts]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error improving prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/images", response_model=ImageResponse)
async def generate_images(project_id: str, request: ImageGenerateRequest):
    """Generate images for all scenes."""
    collection = get_projects_collection()
    image_generator = ImageGenerator()
    
    try:
        # Get project
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        scenes = project.get("scenes", [])
        if not scenes:
            raise HTTPException(status_code=400, detail="No scenes available")
        
        print(f"[Canvas] Generating {len(scenes)} images...")
        
        # Generate images for all scenes
        updated_scenes = await image_generator.generate_scene_images(
            scenes=scenes,
            visual_style=request.visual_style,
            aspect_ratio="16:9",
        )
        
        # Update project
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "scenes": updated_scenes,
                "progress": 60,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        print(f"[Canvas] Generated {len(updated_scenes)} images")
        
        return ImageResponse(scenes=updated_scenes)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error generating images: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/images/{scene_id}", response_model=SingleImageResponse)
async def regenerate_image(project_id: str, scene_id: int, request: ImageRegenerateRequest):
    """Regenerate a single scene image."""
    collection = get_projects_collection()
    image_generator = ImageGenerator()
    
    try:
        # Get project
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        scenes = project.get("scenes", [])
        scene = next((s for s in scenes if s.get("id") == scene_id), None)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # Use custom prompt or existing
        prompt = request.prompt or scene.get("image_prompt") or scene.get("visual_prompt", "")
        
        print(f"[Canvas] Regenerating image for scene {scene_id}...")
        
        # Generate new image
        result = await image_generator.generate_image(
            prompt=prompt,
            aspect_ratio="16:9",
            style=request.visual_style,
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Image generation failed"))
        
        # Update scene in project
        for s in scenes:
            if s.get("id") == scene_id:
                s["image_url"] = result.get("image_url")
                s["image_prompt"] = prompt
                break
        
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "scenes": scenes,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        return SingleImageResponse(
            image_url=result.get("image_url", ""),
            image_prompt=prompt,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error regenerating image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/videos", response_model=VideoResponse)
async def generate_videos(project_id: str):
    """Generate videos for all scenes using their images."""
    collection = get_projects_collection()
    video_generator = VideoGenerator()
    
    try:
        # Get project
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        scenes = project.get("scenes", [])
        if not scenes:
            raise HTTPException(status_code=400, detail="No scenes available")
        
        style = project.get("style", "cinematic")
        
        print(f"[Canvas] Generating {len(scenes)} videos...")
        
        # Generate video for each scene
        updated_scenes = []
        for idx, scene in enumerate(scenes):
            print(f"[Canvas] Generating video {idx + 1}/{len(scenes)}...")
            
            # Build prompt for video generation
            visual_prompt = scene.get("visual_prompt", scene.get("description", ""))
            voiceover = scene.get("voiceover_text", "")
            
            prompt = f"{style} style. {visual_prompt}"
            if voiceover:
                prompt += f' Narrator speaks: "{voiceover}"'
            
            # Check if scene has image for image-to-video
            image_url = scene.get("image_url")
            
            if image_url and not image_url.startswith("https://picsum"):
                # Use image-to-video if we have a real image
                local_path = None
                if "/static/images/" in image_url:
                    filename = image_url.split("/static/images/")[-1]
                    potential_path = f"static/images/{filename}"
                    if os.path.exists(potential_path):
                        local_path = potential_path
                
                if local_path:
                    # Use local image path
                    result = await video_generator.generate_from_image(
                        prompt=prompt,
                        image_path=local_path,
                        duration=8,
                        resolution="720p",
                        aspect_ratio="16:9",
                    )
                else:
                     # Fallback if path invalid
                    result = await video_generator.generate_clip(
                        prompt=prompt,
                        duration=8,
                        use_fast_model=True,
                        resolution="720p",
                        aspect_ratio="16:9",
                    )
            else:
                # Text-to-video fallback
                result = await video_generator.generate_clip(
                    prompt=prompt,
                    duration=8,
                    use_fast_model=True,
                    resolution="720p",
                    aspect_ratio="16:9",
                )
            
            scene_copy = dict(scene)
            if result.get("success"):
                scene_copy["video_url"] = result.get("video_url")
            
            updated_scenes.append(scene_copy)
        
        # Update project
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "scenes": updated_scenes,
                "status": ProjectStatus.COMPOSING.value,
                "progress": 80,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        print(f"[Canvas] Generated {len(updated_scenes)} videos")
        
        return VideoResponse(scenes=updated_scenes)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error generating videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/videos/{scene_id}", response_model=SingleVideoResponse)
async def regenerate_video(project_id: str, scene_id: int, request: VideoRegenerateRequest = VideoRegenerateRequest()):
    """Regenerate a single scene video."""
    collection = get_projects_collection()
    video_generator = VideoGenerator()
    
    try:
        # Get project
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        scenes = project.get("scenes", [])
        scene = next((s for s in scenes if s.get("id") == scene_id), None)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        style = project.get("style", "cinematic")
        visual_prompt = scene.get("visual_prompt", scene.get("description", ""))
        voiceover = scene.get("voiceover_text", "")
        
        # Use provided prompt or build default
        if request.prompt:
            prompt = request.prompt
        else:
            prompt = f"{style} style. {visual_prompt}"
            if voiceover:
                prompt += f' Narrator speaks: "{voiceover}"'
        
        print(f"[Canvas] Regenerating video for scene {scene_id}...")

        # Check for image - prioritize request image (from frontend/last frame) over scene image
        image_url = request.image_url or scene.get("image_url")
        result = None
        
        if image_url and not image_url.startswith("https://picsum"):
             # Logic to resolve path
             if "/static/images/" in image_url:
                 filename = image_url.split("/static/images/")[-1]
                 local_path = f"static/images/{filename}"
                 
                 if os.path.exists(local_path):
                     print(f"[Canvas] Using image for generation: {local_path}")
                     result = await video_generator.generate_from_image(
                         prompt=prompt,
                         image_path=local_path,
                         duration=8,
                         resolution="720p",
                         aspect_ratio="16:9",
                     )
        
        if not result:
            print("[Canvas] Using text-to-video generation")
            result = await video_generator.generate_clip(
                prompt=prompt,
                duration=8,
                use_fast_model=True,
                resolution="720p",
                aspect_ratio="16:9",
            )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Video generation failed"))
        
        # Update scene in project
        for s in scenes:
            if s.get("id") == scene_id:
                s["video_url"] = result.get("video_url")
                break
        
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "scenes": scenes,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        return SingleVideoResponse(video_url=result.get("video_url", ""))
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error regenerating video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/compose", response_model=ComposeResponse)
async def compose_video(project_id: str, request: ComposeRequest):
    """Compose all video clips using Remotion."""
    collection = get_projects_collection()
    video_composer = VideoComposer()
    
    try:
        # Get project
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        scenes = project.get("scenes", [])
        brand_profile = project.get("brand_profile", {})
        story = project.get("story", {})
        
        # Filter scenes with videos
        scenes_with_video = [s for s in scenes if s.get("video_url")]
        if not scenes_with_video:
            raise HTTPException(status_code=400, detail="No video clips available")
        
        print(f"[Canvas] Composing {len(scenes_with_video)} clips...")
        for i, s in enumerate(scenes_with_video):
            print(f"[Canvas]   Scene {i+1}: video_url={s.get('video_url', 'MISSING')[:80]}...")
        
        # Compose video
        preview_url = await video_composer.compose_video(
            project_id=project_id,
            scenes=scenes_with_video,
            brand_profile=brand_profile,
            story=story,
        )
        
        if not preview_url:
            # Fallback to first video
            preview_url = scenes_with_video[0].get("video_url", "")
        
        # Update project
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "composition_url": preview_url,
                "composition_settings": request.model_dump(),
                "progress": 90,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        print(f"[Canvas] Composition complete: {preview_url}")
        
        return ComposeResponse(preview_url=preview_url)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error composing video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/render", response_model=RenderResponse)
async def render_final_video(project_id: str, request: RenderRequest):
    """Render the final high-quality video."""
    collection = get_projects_collection()
    
    try:
        # Get project
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # For now, use composition URL as final
        # In production, this would trigger a high-quality Remotion render
        composition_url = project.get("composition_url")
        if not composition_url:
            scenes = project.get("scenes", [])
            scenes_with_video = [s for s in scenes if s.get("video_url")]
            if scenes_with_video:
                composition_url = scenes_with_video[0].get("video_url", "")
        
        if not composition_url:
            raise HTTPException(status_code=400, detail="No video available to render")
        
        print(f"[Canvas] Final render at {request.resolution}: {composition_url}")
        
        # Update project
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "video_url": composition_url,
                "render_settings": request.model_dump(),
                "status": ProjectStatus.COMPLETED.value,
                "progress": 100,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        return RenderResponse(video_url=composition_url)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Canvas] Error rendering video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/video/extract-frame", response_model=ExtractFrameResponse)
async def extract_video_frame(project_id: str, request: ExtractFrameRequest):
    """Extract the last frame from a video for sequential generation."""
    frame_extractor = FrameExtractor()
    
    try:
        frame_url = await frame_extractor.extract_last_frame(request.video_url)
        return ExtractFrameResponse(frame_url=frame_url)
    except Exception as e:
        print(f"[Canvas] Error extracting frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))
