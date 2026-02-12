"""Generate endpoint - AI content and video generation."""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.core.database import get_projects_collection
from app.agents import BrandAnalyzer, Storyteller, ScriptWriter
from app.services.scraper import WebScraper
from app.services.video_generator import VideoGenerator
from app.models.project import (
    ProjectStatus,
    VideoStyle,
    Story,
    BrandProfile,
)

router = APIRouter()


class GenerateStoryRequest(BaseModel):
    project_id: str


class GenerateVideoRequest(BaseModel):
    prompt: str
    duration: int = 8
    use_fast_model: bool = False


class GenerateAudioRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None


@router.post("/story")
async def generate_story(request: GenerateStoryRequest, background_tasks: BackgroundTasks):
    """
    Generate story and script for a project.
    
    This triggers the full content generation pipeline:
    1. Scrape website (if not done)
    2. Analyze brand
    3. Create story
    4. Write script with scenes
    """
    collection = get_projects_collection()
    
    try:
        oid = ObjectId(request.project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    project = await collection.find_one({"_id": oid})
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Update status
    await collection.update_one(
        {"_id": oid},
        {"$set": {"status": ProjectStatus.PLANNING.value, "updated_at": datetime.now(timezone.utc)}}
    )
    
    # Run generation in background
    background_tasks.add_task(
        run_story_generation,
        str(oid),
        project["website_url"],
        project.get("brand_name"),
        project.get("video_duration", 30),
        VideoStyle(project.get("style", "cinematic")),
        project.get("target_audience"),
        project.get("description"),
    )
    
    return {"message": "Story generation started", "project_id": request.project_id}


async def run_story_generation(
    project_id: str,
    website_url: str,
    brand_name: Optional[str],
    video_duration: int,
    style: VideoStyle,
    target_audience: Optional[str],
    description: Optional[str],
):
    """Background task to generate story and script."""
    collection = get_projects_collection()
    oid = ObjectId(project_id)
    
    try:
        # Step 1: Scrape website
        scraper = WebScraper()
        content = await scraper.scrape(website_url)
        
        # Step 2: Analyze brand
        analyzer = BrandAnalyzer()
        brand_profile = await analyzer.analyze(
            website_content=content.get("main_content", ""),
            website_url=website_url,
            brand_name=brand_name,
        )
        
        # Update with brand profile
        await collection.update_one(
            {"_id": oid},
            {"$set": {"brand_profile": brand_profile.model_dump()}}
        )
        
        # Step 3: Create story
        storyteller = Storyteller()
        story = await storyteller.create_story(
            brand_profile=brand_profile,
            video_duration=video_duration,
            style=style,
            target_audience=target_audience,
            additional_notes=description,
        )
        
        # Update with story
        await collection.update_one(
            {"_id": oid},
            {"$set": {"story": story.model_dump()}}
        )
        
        # Step 4: Write script
        script_writer = ScriptWriter()
        scenes = await script_writer.create_script(
            story=story,
            brand_profile=brand_profile,
            video_duration=video_duration,
            style=style,
        )
        
        # Update with scenes and mark as ready for generation
        await collection.update_one(
            {"_id": oid},
            {
                "$set": {
                    "scenes": [s.model_dump() for s in scenes],
                    "status": ProjectStatus.DRAFT.value,  # Ready for user review
                    "progress": 30,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
    except Exception as e:
        print(f"Story generation error: {e}")
        await collection.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": ProjectStatus.FAILED.value,
                    "error": str(e),
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )


@router.post("/video")
async def generate_video_clip(request: GenerateVideoRequest):
    """
    Generate a single video clip using Veo 3.1.
    
    For testing video generation with custom prompts.
    """
    generator = VideoGenerator()
    
    result = await generator.generate_clip(
        prompt=request.prompt,
        duration=request.duration,
        use_fast_model=request.use_fast_model,
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Video generation failed"))
    
    return result


@router.post("/audio")
async def generate_audio(request: GenerateAudioRequest):
    """
    Generate voiceover audio using ElevenLabs (optional).
    
    Note: Veo 3.1 includes native audio generation. 
    This endpoint is for custom voiceovers if needed later.
    """
    from app.core.config import settings
    
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=501, 
            detail="ElevenLabs not configured. Veo 3.1 generates native audio."
        )
    
    from app.services.audio_generator import AudioGenerator
    generator = AudioGenerator()
    
    result = await generator.generate_voiceover(
        text=request.text,
        voice_id=request.voice_id,
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Audio generation failed"))
    
    return result


@router.get("/voices")
async def list_voices():
    """List available ElevenLabs voices (optional)."""
    from app.core.config import settings
    
    if not settings.elevenlabs_api_key:
        return {"voices": [], "message": "ElevenLabs not configured"}
    
    from app.services.audio_generator import AudioGenerator
    generator = AudioGenerator()
    voices = await generator.list_voices()
    return {"voices": voices}


@router.post("/{project_id}/assets")
async def generate_project_assets(project_id: str, background_tasks: BackgroundTasks):
    """
    Generate all video and audio assets for a project.
    
    Requires story and scenes to be already generated.
    """
    collection = get_projects_collection()
    
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    project = await collection.find_one({"_id": oid})
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.get("scenes"):
        raise HTTPException(status_code=400, detail="No scenes found. Generate story first.")
    
    # Update status
    await collection.update_one(
        {"_id": oid},
        {"$set": {"status": ProjectStatus.GENERATING.value, "updated_at": datetime.now(timezone.utc)}}
    )
    
    # Run asset generation in background
    background_tasks.add_task(run_asset_generation, project_id)
    
    return {"message": "Asset generation started", "project_id": project_id}


async def run_asset_generation(project_id: str):
    """Background task to generate all video assets using Veo 3.1."""
    collection = get_projects_collection()
    oid = ObjectId(project_id)
    
    project = await collection.find_one({"_id": oid})
    scenes = project.get("scenes", [])
    
    video_gen = VideoGenerator()
    
    try:
        total_scenes = len(scenes)
        
        for idx, scene in enumerate(scenes):
            # Generate video for scene (Veo 3.1 includes native audio)
            if scene.get("visual_prompt"):
                # Build prompt with voiceover text for Veo's native audio
                prompt = scene["visual_prompt"]
                if scene.get("voiceover_text"):
                    prompt += f"\n\nNarration: \"{scene['voiceover_text']}\""
                
                video_result = await video_gen.generate_clip(
                    prompt=prompt,
                    duration=min(8, int(scene.get("end_time", 8) - scene.get("start_time", 0))),
                )
                
                if video_result.get("success"):
                    scenes[idx]["asset_url"] = video_result.get("video_url")
            
            # Update progress
            progress = 30 + int((idx + 1) / total_scenes * 50)  # 30-80%
            await collection.update_one(
                {"_id": oid},
                {"$set": {"scenes": scenes, "progress": progress}}
            )
        
        # Mark as ready for composition
        await collection.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": ProjectStatus.COMPOSING.value,
                    "progress": 80,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
    except Exception as e:
        print(f"Asset generation error: {e}")
        await collection.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": ProjectStatus.FAILED.value,
                    "error": str(e),
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
