from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.core.database import get_projects_collection
from app.models.project import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectStatus,
    ProjectWithStages,
    GenerationStage,
)
from app.services.pipeline import run_generation_pipeline

router = APIRouter()


def project_helper(project: dict) -> dict:
    """Convert MongoDB document to API response format."""
    project["id"] = str(project.pop("_id"))
    return project


@router.get("", response_model=List[Project])
async def list_projects(
    status: ProjectStatus | None = None,
    limit: int = 50,
    skip: int = 0,
):
    """List all projects with optional filtering."""
    collection = get_projects_collection()
    
    query = {}
    if status:
        query["status"] = status.value
    
    cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    projects = await cursor.to_list(length=limit)
    
    return [project_helper(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectWithStages)
async def get_project(project_id: str):
    """Get a project by ID with generation stages."""
    collection = get_projects_collection()
    
    try:
        project = await collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_data = project_helper(project)
    
    # Build generation stages based on project status
    stages = build_generation_stages(project_data.get("status", "draft"))
    
    return ProjectWithStages(**project_data, stages=stages)


@router.post("", response_model=Project)
async def create_project(data: ProjectCreate):
    """Create a new project."""
    collection = get_projects_collection()
    now = datetime.now(timezone.utc)
    
    project_doc = {
        "website_url": str(data.website_url),
        "brand_name": data.brand_name,
        "description": data.description,
        "target_audience": data.target_audience,
        "video_duration": data.video_duration,
        "style": data.style.value,
        "status": ProjectStatus.DRAFT.value,
        "progress": 0,
        "brand_profile": None,
        "story": None,
        "scenes": [],
        "video_url": None,
        "thumbnail_url": None,
        "created_at": now,
        "updated_at": now,
    }
    
    result = await collection.insert_one(project_doc)
    project_doc["_id"] = result.inserted_id
    
    return project_helper(project_doc)


@router.patch("/{project_id}", response_model=Project)
async def update_project(project_id: str, data: ProjectUpdate):
    """Update a project (only changed fields)."""
    collection = get_projects_collection()
    
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    # Only update provided fields
    update_data = data.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Convert enum to string if present
    if "style" in update_data and update_data["style"]:
        update_data["style"] = update_data["style"].value
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await collection.find_one_and_update(
        {"_id": oid},
        {"$set": update_data},
        return_document=True,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return project_helper(result)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    collection = get_projects_collection()
    
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    result = await collection.delete_one({"_id": oid})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"message": "Project deleted", "id": project_id}


@router.post("/{project_id}/start")
async def start_generation(project_id: str, background_tasks: BackgroundTasks):
    """Start the video generation pipeline."""
    collection = get_projects_collection()
    
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    project = await collection.find_one({"_id": oid})
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if already generating
    if project.get("status") in [ProjectStatus.ANALYZING.value, ProjectStatus.GENERATING.value, ProjectStatus.PLANNING.value]:
        raise HTTPException(status_code=400, detail="Generation already in progress")
    
    # Update status to analyzing
    await collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": ProjectStatus.ANALYZING.value,
                "progress": 0,
                "error": None,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    
    # Add background task for video generation pipeline
    background_tasks.add_task(run_generation_pipeline, project_id)
    
    return {"message": "Generation started", "project_id": project_id}


def build_generation_stages(status: str) -> List[GenerationStage]:
    """Build generation stages based on current project status."""
    stage_order = [
        ("analyze", "Analyzing Website"),
        ("story", "Crafting Story"),
        ("script", "Writing Script"),
        ("assets", "Generating Assets"),
        ("compose", "Composing Video"),
        ("audio", "Adding Audio"),
        ("finalize", "Final Render"),
    ]
    
    status_to_stage = {
        "draft": -1,
        "analyzing": 0,
        "planning": 1,
        "generating": 3,
        "composing": 4,
        "completed": 7,
        "failed": -2,
    }
    
    current_stage_idx = status_to_stage.get(status, -1)
    
    stages = []
    for idx, (stage_id, label) in enumerate(stage_order):
        if current_stage_idx == -2:  # Failed
            stage_status = "failed" if idx == 0 else "pending"
        elif idx < current_stage_idx:
            stage_status = "completed"
        elif idx == current_stage_idx:
            stage_status = "in_progress"
        else:
            stage_status = "pending"
        
        stages.append(GenerationStage(id=stage_id, label=label, status=stage_status))
    
    return stages
