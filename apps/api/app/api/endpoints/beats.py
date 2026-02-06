"""
Beat API endpoints for granular story flow.
"""
from fastapi import APIRouter, HTTPException, Path, Query
from typing import List, Optional
from pydantic import BaseModel
import uuid

from app.models.beat import (
    Beat, 
    BeatCreate, 
    BeatUpdate, 
    BeatList, 
    BeatsFromStrategy,
    GenerationStatus
)

router = APIRouter(prefix="/api/beats")

# In-memory storage for demo (replace with MongoDB in production)
_beats_store: dict[str, dict[str, Beat]] = {}


class GenerateBeatsRequest(BaseModel):
    """Request to auto-generate beats from strategy."""
    project_id: str
    strategy_objective: str
    content_structure: List[dict]
    target_duration: int = 30


class GenerateBeatsResponse(BaseModel):
    """Response with auto-generated beats."""
    beats: List[Beat]
    message: str


@router.get("/{project_id}", response_model=BeatList)
async def get_beats(
    project_id: str = Path(..., description="Project ID")
) -> BeatList:
    """Get all beats for a project."""
    project_beats = _beats_store.get(project_id, {})
    beats = sorted(project_beats.values(), key=lambda b: b.index)
    return BeatList(beats=beats, total=len(beats))


@router.post("/{project_id}", response_model=Beat)
async def create_beat(
    beat_data: BeatCreate,
    project_id: str = Path(..., description="Project ID")
) -> Beat:
    """Create a new beat for a project."""
    if project_id not in _beats_store:
        _beats_store[project_id] = {}
    
    beat_id = f"beat-{uuid.uuid4().hex[:8]}"
    
    beat = Beat(
        id=beat_id,
        index=beat_data.index,
        name=beat_data.name,
        description=beat_data.description,
        script=beat_data.script,
        visual_prompt=beat_data.visual_prompt,
        duration_seconds=beat_data.duration_seconds,
        purpose=beat_data.purpose,
        hook=beat_data.hook,
        emotional_note=beat_data.emotional_note,
        image_url=None,
        video_url=None,
        generation_status=GenerationStatus.IDLE
    )
    
    _beats_store[project_id][beat_id] = beat
    return beat


@router.get("/{project_id}/{beat_id}", response_model=Beat)
async def get_beat(
    project_id: str = Path(..., description="Project ID"),
    beat_id: str = Path(..., description="Beat ID")
) -> Beat:
    """Get a specific beat."""
    project_beats = _beats_store.get(project_id, {})
    beat = project_beats.get(beat_id)
    
    if not beat:
        raise HTTPException(status_code=404, detail="Beat not found")
    
    return beat


@router.patch("/{project_id}/{beat_id}", response_model=Beat)
async def update_beat(
    beat_data: BeatUpdate,
    project_id: str = Path(..., description="Project ID"),
    beat_id: str = Path(..., description="Beat ID")
) -> Beat:
    """Update a beat."""
    project_beats = _beats_store.get(project_id, {})
    beat = project_beats.get(beat_id)
    
    if not beat:
        raise HTTPException(status_code=404, detail="Beat not found")
    
    # Update fields that are provided
    update_data = beat_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(beat, field, value)
    
    _beats_store[project_id][beat_id] = beat
    return beat


@router.delete("/{project_id}/{beat_id}")
async def delete_beat(
    project_id: str = Path(..., description="Project ID"),
    beat_id: str = Path(..., description="Beat ID")
) -> dict:
    """Delete a beat."""
    project_beats = _beats_store.get(project_id, {})
    
    if beat_id not in project_beats:
        raise HTTPException(status_code=404, detail="Beat not found")
    
    del _beats_store[project_id][beat_id]
    
    # Reindex remaining beats
    remaining_beats = sorted(
        _beats_store[project_id].values(), 
        key=lambda b: b.index
    )
    for i, beat in enumerate(remaining_beats):
        beat.index = i
        _beats_store[project_id][beat.id] = beat
    
    return {"message": "Beat deleted", "beat_id": beat_id}


@router.post("/{project_id}/generate", response_model=GenerateBeatsResponse)
async def generate_beats_from_strategy(
    request: GenerateBeatsRequest,
    project_id: str = Path(..., description="Project ID")
) -> GenerateBeatsResponse:
    """Auto-generate beats from a story strategy's content structure."""
    if project_id not in _beats_store:
        _beats_store[project_id] = {}
    
    # Clear existing beats
    _beats_store[project_id] = {}
    
    beats = []
    total_duration = 0
    
    for i, structure in enumerate(request.content_structure):
        beat_id = f"beat-{uuid.uuid4().hex[:8]}"
        duration = structure.get("duration_seconds", 5)
        
        beat = Beat(
            id=beat_id,
            index=i,
            name=structure.get("name", f"Beat {i + 1}"),
            description=structure.get("description", ""),
            script="",  # To be filled by user or AI
            visual_prompt=f"Visual for {structure.get('name', 'scene')}, {structure.get('purpose', '')}",
            duration_seconds=duration,
            purpose=structure.get("purpose", ""),
            hook=None,
            emotional_note=None,
            image_url=None,
            video_url=None,
            generation_status=GenerationStatus.IDLE
        )
        
        _beats_store[project_id][beat_id] = beat
        beats.append(beat)
        total_duration += duration
    
    return GenerateBeatsResponse(
        beats=beats,
        message=f"Generated {len(beats)} beats with total duration of {total_duration}s"
    )


@router.post("/{project_id}/reorder")
async def reorder_beats(
    project_id: str = Path(..., description="Project ID"),
    beat_order: List[str] = []
) -> BeatList:
    """Reorder beats by providing new order of beat IDs."""
    project_beats = _beats_store.get(project_id, {})
    
    if not project_beats:
        raise HTTPException(status_code=404, detail="No beats found for project")
    
    # Validate all beat IDs exist
    for beat_id in beat_order:
        if beat_id not in project_beats:
            raise HTTPException(status_code=400, detail=f"Beat {beat_id} not found")
    
    # Update indices
    for new_index, beat_id in enumerate(beat_order):
        project_beats[beat_id].index = new_index
    
    beats = sorted(project_beats.values(), key=lambda b: b.index)
    return BeatList(beats=beats, total=len(beats))
