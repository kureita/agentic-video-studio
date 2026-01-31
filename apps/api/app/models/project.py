from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPOSING = "composing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoStyle(str, Enum):
    CINEMATIC = "cinematic"
    MINIMAL = "minimal"
    ENERGETIC = "energetic"
    ELEGANT = "elegant"
    PLAYFUL = "playful"
    CORPORATE = "corporate"


class Scene(BaseModel):
    id: int
    start_time: float
    end_time: float
    description: str
    visual_prompt: str
    voiceover_text: Optional[str] = None
    on_screen_text: Optional[str] = None
    asset_url: Optional[str] = None


class Story(BaseModel):
    title: str
    synopsis: str
    key_messages: List[str]
    target_emotion: str
    call_to_action: str


class BrandProfile(BaseModel):
    name: str
    tagline: Optional[str] = None
    description: Optional[str] = None
    primary_colors: List[str] = []
    logo_url: Optional[str] = None
    tone: str = "professional"
    products: List[str] = []
    unique_selling_points: List[str] = []


class ProjectCreate(BaseModel):
    website_url: HttpUrl
    brand_name: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    video_duration: int = 30
    style: VideoStyle = VideoStyle.CINEMATIC


class ProjectUpdate(BaseModel):
    brand_name: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    video_duration: Optional[int] = None
    style: Optional[VideoStyle] = None


class Project(BaseModel):
    id: str
    website_url: str
    brand_name: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    video_duration: int
    style: VideoStyle
    status: ProjectStatus
    progress: int = 0
    brand_profile: Optional[BrandProfile] = None
    story: Optional[Story] = None
    scenes: List[Scene] = []
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GenerationStage(BaseModel):
    id: str
    label: str
    status: str  # pending, in_progress, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class ProjectWithStages(Project):
    stages: List[GenerationStage] = []

