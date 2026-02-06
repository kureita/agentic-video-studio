"""
Beat model for granular story flow.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class GenerationStatus(str, Enum):
    IDLE = "idle"
    GENERATING = "generating"
    COMPLETE = "complete"
    ERROR = "error"


class BeatBase(BaseModel):
    """Base beat model with common fields."""
    name: str = Field(..., description="Beat name/title")
    description: str = Field(..., description="What happens in this beat")
    script: str = Field("", description="Voiceover/dialogue script")
    visual_prompt: str = Field("", description="Visual prompt for image generation")
    duration_seconds: int = Field(5, ge=1, le=60, description="Beat duration in seconds")
    purpose: str = Field("", description="Narrative purpose of the beat")
    hook: Optional[str] = Field(None, description="Hook/attention grabber if any")
    emotional_note: Optional[str] = Field(None, description="Emotional tone for this beat")


class BeatCreate(BeatBase):
    """Model for creating a new beat."""
    index: int = Field(..., ge=0, description="Position in the story sequence")


class BeatUpdate(BaseModel):
    """Model for updating a beat."""
    name: Optional[str] = None
    description: Optional[str] = None
    script: Optional[str] = None
    visual_prompt: Optional[str] = None
    duration_seconds: Optional[int] = Field(None, ge=1, le=60)
    purpose: Optional[str] = None
    hook: Optional[str] = None
    emotional_note: Optional[str] = None
    index: Optional[int] = Field(None, ge=0)


class Beat(BeatBase):
    """Full beat model with all fields."""
    id: str = Field(..., description="Unique beat identifier")
    index: int = Field(..., ge=0, description="Position in the story sequence")
    image_url: Optional[str] = Field(None, description="Generated image URL")
    video_url: Optional[str] = Field(None, description="Generated video URL")
    generation_status: GenerationStatus = Field(
        GenerationStatus.IDLE, 
        description="Current generation status"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "beat-1",
                "index": 0,
                "name": "Hook",
                "description": "Attention-grabbing opening",
                "script": "Have you ever wondered...",
                "visual_prompt": "Close-up of a curious face, cinematic lighting",
                "duration_seconds": 3,
                "purpose": "capture_attention",
                "hook": "Question hook",
                "emotional_note": "curiosity",
                "image_url": None,
                "video_url": None,
                "generation_status": "idle"
            }
        }


class BeatList(BaseModel):
    """List of beats for a project."""
    beats: List[Beat] = Field(default_factory=list)
    total: int = Field(0)


class BeatsFromStrategy(BaseModel):
    """Request to generate beats from a story strategy."""
    strategy_objective: str
    content_structure: List[dict]  # ContentBeat objects from strategy
    target_duration: int = Field(30, ge=5, le=300)
