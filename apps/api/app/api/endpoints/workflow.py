"""Workflow CRUD and Execution Endpoints."""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

from app.core.database import get_database, get_workflow_jobs_collection, get_fal_jobs_collection
from app.core.auth import get_current_user
from app.services.node_runner import NodeRunner
from app.services.billing import BillingService
from app.services.fal_context import set_context, reset_context
from app.models.usage import ActionType
from app.api.endpoints.user_assets import _is_media_url
from app.models.workflow_job import (
    JobTask, CreateJobResponse, JobTaskStatus, JobStatusResponse, JobProcessorRequest
)

router = APIRouter()


# ============================================
# Request/Response Models
# ============================================

class NodePosition(BaseModel):
    x: float
    y: float


class WorkflowNode(BaseModel):
    id: str
    type: str
    position: NodePosition
    data: Dict[str, Any] = {}


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None


class CreateWorkflowRequest(BaseModel):
    name: Optional[str] = "Untitled Workflow"


class ToolCallData(BaseModel):
    name: str
    status: str = "completed"  # "running", "completed", "failed"
    args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None


class ChatAttachment(BaseModel):
    filename: str
    type: str
    url: str


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None
    attachments: Optional[List[ChatAttachment]] = None
    # Rich assistant message metadata
    thinking: Optional[str] = None
    thinking_duration_ms: Optional[int] = None
    tool_calls: Optional[List[ToolCallData]] = None


class UpdateWorkflowRequest(BaseModel):
    name: Optional[str] = None
    nodes: Optional[List[WorkflowNode]] = None
    edges: Optional[List[WorkflowEdge]] = None
    chat_history: Optional[List[ChatMessage]] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    outputs: Dict[str, Any] = {}
    chat_history: List[Dict[str, Any]] = []
    is_public: bool = False
    created_at: str
    updated_at: str


class WorkflowListItem(BaseModel):
    id: str
    name: str
    updated_at: str
    node_count: int = 0
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    thumbnail_url: Optional[str] = None
    status: str = "draft"  # draft | generating | ready | failed


class RunNodeRequest(BaseModel):
    """Request body for running a node - allows passing input overrides."""
    input_overrides: Optional[Dict[str, Any]] = None


class RunNodeResponse(BaseModel):
    success: bool
    node_id: str
    output: Optional[Any] = None
    error: Optional[str] = None
    start_frame: Optional[str] = None  # Extracted first frame (videoGen only)
    end_frame: Optional[str] = None    # Extracted last frame (videoGen only)


class RunWorkflowResponse(BaseModel):
    success: bool
    outputs: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []


# --- Async Run Models ---

class NodeState(BaseModel):
    """Status of a single node during async execution."""
    status: str  # "queued", "running", "completed", "failed", "skipped"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class RunWorkflowAsyncResponse(BaseModel):
    """Response from starting an async workflow run."""
    run_id: str
    status: str = "running"


class WorkflowRunStatus(BaseModel):
    """Response from polling async workflow run status."""
    run_id: str
    status: str  # "running", "completed", "failed"
    node_states: Dict[str, NodeState] = {}
    outputs: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []
    progress: Dict[str, int] = {}  # {"current": 3, "total": 7}


# ============================================
# Helper Functions
# ============================================

def get_workflows_collection():
    """Get the workflows MongoDB collection."""
    db = get_database()
    return db["workflows"]


def ensure_utc_isoformat(dt):
    """Ensure datetime has UTC timezone before converting to ISO format."""
    if not isinstance(dt, datetime):
        return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

def serialize_workflow(workflow: dict) -> dict:
    """Convert MongoDB document to response format."""
    # Ensure nodes and edges are always lists
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    chat_history = workflow.get("chat_history", [])
    
    # Validate nodes structure
    if not isinstance(nodes, list):
        print(f"[Workflow] Warning: nodes is not a list, got {type(nodes)}")
        nodes = []
    
    # Validate edges structure
    if not isinstance(edges, list):
        print(f"[Workflow] Warning: edges is not a list, got {type(edges)}")
        edges = []
    
    # Validate chat_history structure
    if not isinstance(chat_history, list):
        print(f"[Workflow] Warning: chat_history is not a list, got {type(chat_history)}")
        chat_history = []
    return {
        "id": str(workflow.get("_id")) if "_id" in workflow else workflow.get("id"),
        "name": workflow.get("name", "Untitled Workflow"),
        "nodes": nodes,
        "edges": edges,
        "outputs": workflow.get("outputs", {}),
        "chat_history": chat_history,
        "is_public": workflow.get("is_public", False),
        "created_at": ensure_utc_isoformat(workflow.get("created_at", datetime.now(timezone.utc))),
        "updated_at": ensure_utc_isoformat(workflow.get("updated_at", datetime.now(timezone.utc))),
    }
    
import re

def presign_urls(data: Any, s3_service=None) -> Any:
    """Helper to recursively presign all s3 url strings in an object.
    
    Handles both raw S3 URLs and already-presigned URLs (strips old signature first).
    """
    from app.services.storage_service import S3StorageService
    if s3_service is None:
        s3_service = S3StorageService()
    
    if isinstance(data, dict):
        return {k: presign_urls(v, s3_service) for k, v in data.items()}
    elif isinstance(data, list):
        return [presign_urls(item, s3_service) for item in data]
    elif isinstance(data, str) and S3StorageService.is_s3_url(data):
        # If it's precisely a URL
        if data.startswith("http") and not (" " in data or "\n" in data):
            return s3_service.get_presigned_url(data)
        else:
            # Extract and presign S3 URLs embedded in markdown, TSX code, or JSON strings.
            # The \\ exclusion prevents eating JSON escape backslashes before quotes.
            pattern = r'(https://[^"\s\'\>\)\\]*kureita[^"\s\'\>\)\\]*amazonaws\.com[^"\s\'\>\)\\]+)'
            def replacer(match):
                url = match.group(1)
                return s3_service.get_presigned_url(url)
            return re.sub(pattern, replacer, data)
    else:
        return data


def strip_presigned_from_data(data: Any) -> Any:
    """Recursively strip presigned URL params from all S3 URLs in an object.
    
    This ensures we only store raw S3 keys/URLs in MongoDB, never signed URLs.
    """
    from app.services.storage_service import S3StorageService
    
    if isinstance(data, dict):
        return {k: strip_presigned_from_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [strip_presigned_from_data(item) for item in data]
    elif isinstance(data, str) and S3StorageService.is_s3_url(data):
        if data.startswith("http") and not (" " in data or "\n" in data):
            return S3StorageService.strip_presigned_params(data)
        else:
            # Handle markdown strings with embedded URLs
            pattern = r'(https://[^"\s\'\>\)]*kureita[^"\s\'\>\)]*amazonaws\.com[^"\s\'\>\)]+)'
            def replacer(match):
                url = match.group(1)
                return S3StorageService.strip_presigned_params(url)
            return re.sub(pattern, replacer, data)
    else:
        return data


# ============================================
# CRUD Endpoints
# ============================================

@router.post("", response_model=WorkflowResponse)
async def create_workflow(request: CreateWorkflowRequest, current_user: dict = Depends(get_current_user)):
    """Create a new workflow."""
    collection = get_workflows_collection()
    
    name = request.name
    if not name or name == "Untitled Workflow":
        doc_count = await collection.count_documents({
            "user_id": current_user.get("_id"),
            "name": {"$regex": "^Untitled Workflow(-\\d+)?$"}
        })
        name = f"Untitled Workflow-{doc_count + 1}"

    now = datetime.now(timezone.utc)
    workflow_data = {
        "name": name,
        "user_id": current_user.get("_id"),
        "nodes": [],
        "edges": [],
        "outputs": {},
        "chat_history": [],
        "created_at": now,
        "updated_at": now,
    }
    
    result = await collection.insert_one(workflow_data)
    workflow_data["_id"] = result.inserted_id
    
    print(f"[Workflow] Created workflow: {result.inserted_id}")
    
    return presign_urls(serialize_workflow(workflow_data))


@router.get("", response_model=List[WorkflowListItem])
async def list_workflows(current_user: dict = Depends(get_current_user)):
    """List all workflows for the current user."""
    collection = get_workflows_collection()
    
    # Show user's own workflows + legacy workflows without user_id
    user_id = current_user.get("_id")
    query = {"$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]}
    cursor = collection.find(query).sort("updated_at", -1)
    workflows = await cursor.to_list(length=100)
    
    result = []
    for w in workflows:
        # ── Derive thumbnail_url ──
        # Priority: first imageGen output → first mediaUpload output → None
        thumbnail_url = None
        outputs = w.get("outputs", {})
        nodes_list = w.get("nodes", [])
        
        # Build a map of node_id → type for quick lookup
        node_type_map = {n.get("id"): n.get("type") for n in nodes_list}
        
        # Look for imageGen outputs first (best thumbnails)
        for node_id, output_val in outputs.items():
            if node_type_map.get(node_id) == "imageGen" and isinstance(output_val, str) and output_val.startswith("http"):
                thumbnail_url = output_val
                break
        
        # Fallback to mediaUpload
        if not thumbnail_url:
            for node_id, output_val in outputs.items():
                if node_type_map.get(node_id) == "mediaUpload" and isinstance(output_val, str) and output_val.startswith("http"):
                    thumbnail_url = output_val
                    break
        
        # ── Derive status ──
        execution = w.get("execution", {})
        exec_status = execution.get("status") if execution else None
        
        if exec_status == "running":
            status = "generating"
        elif exec_status == "failed":
            status = "failed"
        elif exec_status == "completed":
            status = "ready"
        elif any(outputs.values()):
            # Has some outputs but no execution tracking → likely ran before polling was added
            status = "ready"
        else:
            status = "draft"
        
        from app.services.storage_service import S3StorageService
        s3_service = S3StorageService()
        if thumbnail_url and "kureita.s3" in thumbnail_url:
            thumbnail_url = s3_service.get_presigned_url(thumbnail_url)
            
        result.append(
            WorkflowListItem(
                id=str(w["_id"]),
                name=w.get("name", "Untitled Workflow"),
                updated_at=ensure_utc_isoformat(w.get("updated_at", datetime.now(timezone.utc))),
                node_count=len(nodes_list),
                nodes=[
                    {"id": n.get("id"), "type": n.get("type"), "position": n.get("position", {})}
                    for n in nodes_list
                ],
                edges=[
                    {"id": e.get("id"), "source": e.get("source"), "target": e.get("target")}
                    for e in w.get("edges", [])
                ],
                thumbnail_url=thumbnail_url,
                status=status,
            )
        )
    
    return result


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, current_user: dict = Depends(get_current_user)):
    """Get a workflow by ID."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    user_id = current_user.get("_id")
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })
    
    if not workflow:
        print(f"[Workflow] Workflow not found: {workflow_id}")
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    serialized = presign_urls(serialize_workflow(workflow))
    print(f"[Workflow] Retrieved workflow {workflow_id}: {len(serialized['nodes'])} nodes, {len(serialized['edges'])} edges")
    
    return serialized


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str, 
    request: UpdateWorkflowRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update a workflow (name, nodes, edges)."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    # Build update document
    update_data: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    
    if request.name is not None:
        update_data["name"] = request.name
    if request.nodes is not None:
        # Strip presigned params from node data before saving to MongoDB
        update_data["nodes"] = strip_presigned_from_data([node.model_dump() for node in request.nodes])
    if request.edges is not None:
        update_data["edges"] = [edge.model_dump() for edge in request.edges]
    if request.chat_history is not None:
        # Strip presigned params from attachment URLs before persisting.
        # Fresh presigned URLs are generated when reading workflow data.
        update_data["chat_history"] = strip_presigned_from_data(
            [msg.model_dump() for msg in request.chat_history]
        )
    
    user_id = current_user.get("_id")
    query = {
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    }
    
    result = await collection.update_one(
        query,
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Return updated workflow
    workflow = await collection.find_one({"_id": oid})

    if request.name is not None:
        try:
            assets_collection = get_database()["user_assets"]
            await assets_collection.update_many(
                {"user_id": user_id, "workflow_id": workflow_id},
                {"$set": {"workflow_name": workflow.get("name", "Untitled Workflow")}},
            )
        except Exception as asset_sync_err:
            print(f"[Workflow] ⚠️ Failed to sync asset workflow names for {workflow_id}: {asset_sync_err}")

    serialized = presign_urls(serialize_workflow(workflow))
    
    print(f"[Workflow] Updated workflow: {workflow_id}")
    
    return serialized


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a workflow."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    user_id = current_user.get("_id")
    query = {
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    }
    
    result = await collection.delete_one(query)
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    print(f"[Workflow] Deleted workflow: {workflow_id}")
    
    return {"success": True, "message": "Workflow deleted"}


# ============================================
# Execution Endpoints
# ============================================

@router.post("/{workflow_id}/nodes/{node_id}/run", response_model=RunNodeResponse)
async def run_node(
    workflow_id: str, 
    node_id: str, 
    request: RunNodeRequest = None,
    current_user: dict = Depends(get_current_user)
):
    """Run a single node in a workflow."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    user_id = current_user.get("_id")
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    outputs = workflow.get("outputs", {})
    
    # Find the target node
    target_node = next((n for n in nodes if n["id"] == node_id), None)
    if not target_node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Map node types to action types for billing
    node_type = target_node.get("type")
    action_type_map = {
        "imageGen": ActionType.IMAGE_GEN,
        "videoGen": ActionType.VIDEO_GEN,
        "audioGen": ActionType.AUDIO_GEN,
        "editorAgent": ActionType.RENDER,
    }
    
    print(f"[Workflow] Running node: {node_id} (type: {target_node.get('type')})")
    
    # Run the node
    runner = NodeRunner()
    result = await runner.run_node(
        node=target_node,
        nodes=nodes,
        edges=edges,
        outputs=outputs,
        input_overrides=request.input_overrides if request else None,
        strict_model_selection=True,
    )
    
    if result.get("success"):
        # Charge based on actual API cost (after execution)
        cost = result.get("cost", 0.0)
        if node_type in action_type_map and cost > 0:
            billing_service = BillingService(get_database())
            
            node_data = target_node.get("data", {})
            meta = {
                "workflow_id": workflow_id,
                "node_id": node_id,
                "node_type": node_type
            }
            if node_type == "imageGen":
                meta["ratio"] = node_data.get("ratio", "1:1")
            elif node_type == "videoGen":
                meta["resolution"] = node_data.get("resolution", "720p")
                meta["duration"] = node_data.get("duration", "4s")
            if "prompt" in node_data:
                meta["prompt"] = node_data["prompt"]

            await billing_service.charge_usage(
                user_id=user_id,
                action=action_type_map[node_type],
                cost_usd=cost,
                model_name=result.get("model", node_type),
                provider=result.get("provider", "fal.ai"),
                metadata=meta,
            )
        
        # Update outputs in database
        # First, get the current outputs object
        workflow = await collection.find_one({"_id": oid})
        current_outputs = workflow.get("outputs", {})
        current_outputs[node_id] = result.get("output")
        
        # Also store extracted frames for videoGen nodes
        start_frame = result.get("start_frame")
        end_frame = result.get("end_frame")
        if start_frame:
            current_outputs[f"{node_id}__start_frame"] = start_frame
        if end_frame:
            current_outputs[f"{node_id}__end_frame"] = end_frame
        
        # Update the entire outputs object to avoid creating separate fields
        await collection.update_one(
            {"_id": oid},
            {"$set": {"outputs": current_outputs, "updated_at": datetime.now(timezone.utc)}}
        )
        
        # Register asset in persistent user_assets collection
        new_output = result.get("output")
        if new_output and isinstance(new_output, str) and _is_media_url(new_output):
            try:
                from app.api.endpoints.user_assets import register_asset
                wf_name = workflow.get("name", "Untitled Workflow")
                await register_asset(
                    user_id=user_id,
                    workflow_id=workflow_id,
                    workflow_name=wf_name,
                    node_id=node_id,
                    node_type=node_type,
                    asset_url=new_output,
                    node_data=target_node.get("data"),
                )
            except Exception as reg_err:
                print(f"[Workflow] ⚠️ Asset registration failed: {reg_err}")
        
        print(f"[Workflow] Node {node_id} completed successfully")
    else:
        print(f"[Workflow] Node {node_id} failed: {result.get('error')}")
    
    output_val = result.get("output")
    if result.get("success") and isinstance(output_val, str) and "kureita.s3" in output_val:
        from app.services.storage_service import S3StorageService
        output_val = S3StorageService().get_presigned_url(output_val)
        
    return RunNodeResponse(
        success=result.get("success", False),
        node_id=node_id,
        output=output_val,
        error=result.get("error"),
        start_frame=result.get("start_frame"),
        end_frame=result.get("end_frame"),
    )


class ExtractFramesRequest(BaseModel):
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None

from app.services.storage_service import StorageService
from app.core.dependencies import get_storage_service

@router.post("/{workflow_id}/nodes/{node_id}/extract-frames")
async def extract_frames(
    workflow_id: str,
    node_id: str,
    payload: ExtractFramesRequest,
    current_user: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service)
):
    """Save client-extracted frames for a node's video output.
    
    The frames are expected to be base64 data URIs.
    """
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    user_id = current_user.get("_id")
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    outputs = workflow.get("outputs", {})
    
    # Return cached frames if already extracted
    existing_start = outputs.get(f"{node_id}__start_frame")
    existing_end = outputs.get(f"{node_id}__end_frame")
    if existing_start and existing_end:
        print(f"[ExtractFrames] Returning cached frames for node {node_id}")
        return {"success": True, "start_frame": existing_start, "end_frame": existing_end, "cached": True}
    
    # Helper to decode base64 and save to storage
    import base64
    import uuid
    async def _save_frame(b64_str: str, prefix: str) -> str:
        if not b64_str.startswith("data:image"):
            return b64_str
        try:
            header, encoded = b64_str.split(",", 1)
            ext = ".jpg" if "jpeg" in header or "jpg" in header else ".png"
            content_type = header.split(";")[0].split(":")[1]
            file_bytes = base64.b64decode(encoded)
            filename = f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"
            return await storage.upload_file(file_bytes, filename, content_type)
        except Exception as e:
            print(f"Failed to save frame: {e}")
            return b64_str

    # Persist client-provided frames instantly
    set_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    start_frame_url = payload.start_frame
    end_frame_url = payload.end_frame

    if start_frame_url:
        start_frame_url = await _save_frame(start_frame_url, f"frame_start_{node_id}")
        set_fields[f"outputs.{node_id}__start_frame"] = start_frame_url
    if end_frame_url:
        end_frame_url = await _save_frame(end_frame_url, f"frame_end_{node_id}")
        set_fields[f"outputs.{node_id}__end_frame"] = end_frame_url
    
    if len(set_fields) > 1:
        await collection.update_one({"_id": oid}, {"$set": set_fields})
    
    print(f"[ExtractFrames] Done saving frames for node {node_id}")
    return {
        "success": True, 
        "start_frame": start_frame_url, 
        "end_frame": end_frame_url, 
        "cached": False
    }


@router.delete("/{workflow_id}/nodes/{node_id}/output")
async def clear_node_output(
    workflow_id: str,
    node_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Clear a node's stored output plus any derived start/end frame outputs."""
    collection = get_workflows_collection()

    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")

    user_id = current_user.get("_id")
    query = {
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}],
    }

    workflow = await collection.find_one(query)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    updated_nodes = []
    for node in workflow.get("nodes", []):
        if node.get("id") != node_id:
            updated_nodes.append(node)
            continue

        node_copy = dict(node)
        node_data = dict(node_copy.get("data", {}) or {})
        node_data.pop("output", None)
        node_copy["data"] = node_data
        updated_nodes.append(node_copy)

    unset_fields = {
        f"outputs.{node_id}": "",
        f"outputs.{node_id}__start_frame": "",
        f"outputs.{node_id}__end_frame": "",
        f"execution.outputs.{node_id}": "",
        f"execution.outputs.{node_id}__start_frame": "",
        f"execution.outputs.{node_id}__end_frame": "",
    }

    await collection.update_one(
        query,
        {
            "$unset": unset_fields,
            "$set": {
                "nodes": updated_nodes,
                "updated_at": datetime.now(timezone.utc),
            },
        },
    )

    return {"success": True}


@router.post("/{workflow_id}/run", response_model=RunWorkflowResponse)
async def run_workflow(workflow_id: str, current_user: dict = Depends(get_current_user)):
    """Run the entire workflow by executing nodes in topological order."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    user_id = current_user.get("_id")
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    outputs: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []
    
    print(f"[Workflow] Running workflow: {workflow_id} with {len(nodes)} nodes")
    
    # Sort nodes topologically (simple approach: run nodes with no incoming edges first)
    execution_order = get_topological_order(nodes, edges)
    
    runner = NodeRunner()
    
    action_type_map = {
        "imageGen": ActionType.IMAGE_GEN,
        "videoGen": ActionType.VIDEO_GEN,
        "audioGen": ActionType.AUDIO_GEN,
        "editorAgent": ActionType.RENDER,
    }
    
    for node_id in execution_order:
        node = next((n for n in nodes if n["id"] == node_id), None)
        if not node:
            continue
        
        print(f"[Workflow] Executing node: {node_id} (type: {node.get('type')})")
        
        result = await runner.run_node(
            node=node,
            nodes=nodes,
            edges=edges,
            outputs=outputs,
        )
        
        if result.get("success"):
            outputs[node_id] = result.get("output")
            
            # Billing
            cost = result.get("cost", 0.0)
            node_type = node.get("type")
            if node_type in action_type_map and cost > 0:
                try:
                    billing_service = BillingService(get_database())
                    node_data = node.get("data", {})
                    meta = {"workflow_id": workflow_id, "node_id": node_id, "node_type": node_type}
                    if node_type == "imageGen":
                        meta["ratio"] = node_data.get("ratio", "1:1")
                    elif node_type == "videoGen":
                        meta["resolution"] = node_data.get("resolution", "720p")
                        meta["duration"] = node_data.get("duration", "4s")
                    if "prompt" in node_data:
                        meta["prompt"] = node_data["prompt"]

                    await billing_service.charge_usage(
                        user_id=user_id,
                        action=action_type_map[node_type],
                        cost_usd=cost,
                        model_name=result.get("model", node_type),
                        provider=result.get("provider", "fal.ai"),
                        metadata=meta,
                    )
                    print(f"[Workflow] ✅ Billed ${cost:.4f} for {node_type}")
                except Exception as billing_err:
                    print(f"[Workflow] ⚠️ Billing failed: {billing_err}")
        else:
            errors.append({
                "node_id": node_id,
                "error": result.get("error", "Unknown error"),
            })
    
    # Save all outputs to database
    await collection.update_one(
        {"_id": oid},
        {"$set": {"outputs": outputs, "updated_at": datetime.now(timezone.utc)}}
    )
    
    # Register all generated assets in persistent user_assets collection
    wf_name = workflow.get("name", "Untitled Workflow")
    node_type_map = {n.get("id"): n.get("type") for n in nodes}
    node_data_map = {n.get("id"): n.get("data") for n in nodes}
    for nid, output_val in outputs.items():
        if "__" in nid:
            continue
        if isinstance(output_val, str) and _is_media_url(output_val):
            try:
                from app.api.endpoints.user_assets import register_asset
                await register_asset(
                    user_id=user_id,
                    workflow_id=workflow_id,
                    workflow_name=wf_name,
                    node_id=nid,
                    node_type=node_type_map.get(nid, "mediaUpload"),
                    asset_url=output_val,
                    node_data=node_data_map.get(nid),
                )
            except Exception as reg_err:
                print(f"[Workflow] ⚠️ Asset registration failed for {nid}: {reg_err}")
    
    print(f"[Workflow] Workflow completed. Outputs: {len(outputs)}, Errors: {len(errors)}")
    
    presigned_outputs = presign_urls(outputs)
    
    return RunWorkflowResponse(
        success=len(errors) == 0,
        outputs=presigned_outputs,
        errors=errors,
    )


def get_topological_order(nodes: List[Dict], edges: List[Dict]) -> List[str]:
    """Get nodes in topological order (dependencies first)."""
    # Build adjacency list and in-degree count
    in_degree = {n["id"]: 0 for n in nodes}
    adjacency = {n["id"]: [] for n in nodes}
    
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in adjacency and target in in_degree:
            adjacency[source].append(target)
            in_degree[target] += 1
    
    # Kahn's algorithm
    queue = [nid for nid, degree in in_degree.items() if degree == 0]
    result = []
    
    while queue:
        node_id = queue.pop(0)
        result.append(node_id)
        
        for neighbor in adjacency.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # If there are remaining nodes, there's a cycle - add them anyway
    for node in nodes:
        if node["id"] not in result:
            result.append(node["id"])
    
    return result


# ============================================
# Async Workflow Execution (Polling-based)
# ============================================

# Strong-reference set to prevent asyncio from GC-ing background tasks before they complete
_running_tasks: set = set()

# ── Lambda self-invocation helpers ────────────────────────────────────────────

def _get_lambda_function_name() -> Optional[str]:
    """Return this Lambda's function name (set automatically by AWS runtime)."""
    return os.environ.get("AWS_LAMBDA_FUNCTION_NAME")


async def _invoke_node_lambda(
    workflow_id: str,
    node_id: str,
    run_id: str,
    input_overrides: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Fire-and-forget: invoke THIS Lambda asynchronously (InvocationType=Event)
    to execute a single node in a brand-new Lambda context with its own
    15-minute timeout and its own CloudWatch log stream.

    Falls back to asyncio.create_task() when running locally (no Lambda env).
    """
    function_name = _get_lambda_function_name()

    if not function_name:
        # Local dev: fall back to asyncio background task
        print(f"[NodeAsync] Local mode — using asyncio.create_task for node {node_id}")
        task = asyncio.create_task(_execute_node_async(workflow_id, node_id, run_id, input_overrides))
        _running_tasks.add(task)
        task.add_done_callback(_running_tasks.discard)
        return True

    # Build a minimal HTTP-style payload that the /execute-background endpoint expects
    payload = {
        "workflow_id": workflow_id,
        "node_id": node_id,
        "run_id": run_id,
        "input_overrides": input_overrides or {},
        # Internal secret so the endpoint rejects external calls
        "invoke_secret": os.environ.get("LAMBDA_INVOKE_SECRET", "kureita-internal"),
    }

    # Wrap in a fake API Gateway event so Lambda Web Adapter routes it correctly
    api_gw_event = {
        "version": "2.0",
        "routeKey": "POST /api/workflows/execute-background",
        "rawPath": "/api/workflows/execute-background",
        "rawQueryString": "",
        "headers": {
            "content-type": "application/json",
            "x-invoke-source": "lambda-self",
        },
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/api/workflows/execute-background",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "lambda-self-invoke",
            },
            "accountId": os.environ.get("AWS_ACCOUNT_ID", ""),
            "requestId": run_id,
            "stage": "$default",
            "apiId": "self",
        },
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }

    try:
        import boto3
        lambda_client = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",   # async fire-and-forget
            Payload=json.dumps(api_gw_event).encode("utf-8"),
        )
        status = response.get("StatusCode")
        print(f"[NodeAsync] Lambda self-invoke dispatched for node {node_id} — status: {status}")
        return status == 202  # 202 = accepted (async invoke)
    except Exception as e:
        print(f"[NodeAsync] ❌ Lambda self-invoke failed for node {node_id}: {e}")
        # Fallback: run in current Lambda (risky but better than nothing)
        task = asyncio.create_task(_execute_node_async(workflow_id, node_id, run_id, input_overrides))
        _running_tasks.add(task)
        task.add_done_callback(_running_tasks.discard)
        return False

async def _execute_node_async(workflow_id: str, node_id: str, run_id: str, input_overrides: Optional[Dict[str, Any]] = None):
    """
    Background task: execute a single node,
    updating its status in MongoDB so the frontend can poll.
    """
    print(f"[NodeAsync] ▶ _execute_node_async START: workflow={workflow_id}, node={node_id}, run_id={run_id}")
    collection = get_workflows_collection()
    oid = ObjectId(workflow_id)
    
    workflow = await collection.find_one({"_id": oid})
    if not workflow:
        print(f"[NodeAsync] ❌ Workflow {workflow_id} not found — aborting background task")
        return
    
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    outputs = workflow.get("outputs", {})
    
    target_node = next((n for n in nodes if n["id"] == node_id), None)
    if not target_node:
        # Mark as failed
        await collection.update_one(
            {"_id": oid},
            {"$set": {
                f"execution.node_states.{node_id}.status": "failed",
                f"execution.node_states.{node_id}.error": "Node not found",
            }}
        )
        return
        
    user_id = workflow.get("user_id")

    # Map node types to action types for billing
    node_type = target_node.get("type")
    action_type_map = {
        "imageGen": ActionType.IMAGE_GEN,
        "videoGen": ActionType.VIDEO_GEN,
        "audioGen": ActionType.AUDIO_GEN,
        "editorAgent": ActionType.RENDER,
    }

    print(f"[NodeAsync] 🚀 Calling runner.run_node for: {node_id} (type: {target_node.get('type')}) (run_id: {run_id})")
    runner = NodeRunner()
    
    # Mark node as "running"
    now = datetime.now(timezone.utc).isoformat()
    await collection.update_one(
        {"_id": oid},
        {"$set": {
            f"execution.node_states.{node_id}.status": "running",
            f"execution.node_states.{node_id}.started_at": now,
            "execution.status": "running",
            "execution.run_id": run_id,
        }}
    )
    
    # Set fal webhook context so fal-backed generators can submit async and defer
    # completion to the webhook handler instead of sync-draining the queue.
    # (Without this ctx, FalService takes the "sync-drain" path which fails with
    # "fal job stuck in IN_QUEUE" whenever fal doesn't complete in <~1s.)
    ctx_token = set_context({
        "run_id": run_id,
        "node_id": node_id,
        "node_type": node_type or "",
        "user_id": str(user_id) if user_id else "",
        "workflow_id": workflow_id,
    })

    try:
        result = await runner.run_node(
            node=target_node,
            nodes=nodes,
            edges=edges,
            outputs=outputs,
            input_overrides=input_overrides,
            strict_model_selection=True,
        )
        
        completed_at = datetime.now(timezone.utc).isoformat()
        
        # ── Webhook path: job enqueued on fal; keep node "running" until webhook finalizes it.
        if result.get("success") and result.get("status") == "pending_fal":
            await collection.update_one(
                {"_id": oid},
                {"$set": {
                    f"execution.node_states.{node_id}.status": "running",
                    f"execution.node_states.{node_id}.fal_request_id": result.get("request_id"),
                    f"execution.node_states.{node_id}.fal_endpoint_id": result.get("endpoint_id"),
                    "execution.status": "running",
                    "updated_at": datetime.now(timezone.utc),
                }}
            )
            print(
                f"[NodeAsync] Node {node_id} deferred to webhook "
                f"(request_id={result.get('request_id')})"
            )
            return

        if result.get("success"):
            # Charge based on actual API cost (after execution)
            cost = result.get("cost", 0.0)
            if node_type in action_type_map and cost > 0:
                try:
                    billing_service = BillingService(get_database())

                    node_data = target_node.get("data", {})
                    meta = {
                        "workflow_id": workflow_id,
                        "node_id": node_id,
                        "node_type": node_type
                    }
                    if node_type == "imageGen":
                        meta["ratio"] = node_data.get("ratio", "1:1")
                    elif node_type == "videoGen":
                        meta["resolution"] = node_data.get("resolution", "720p")
                        meta["duration"] = node_data.get("duration", "4s")
                    if "prompt" in node_data:
                        meta["prompt"] = node_data["prompt"]

                    await billing_service.charge_usage(
                        user_id=user_id,
                        action=action_type_map[node_type],
                        cost_usd=cost,
                        model_name=result.get("model", node_type),
                        provider=result.get("provider", "fal.ai"),
                        metadata=meta,
                    )
                    print(f"[NodeAsync] ✅ Billed ${cost:.4f} for {node_type}")
                except Exception as billing_err:
                    print(f"[NodeAsync] ⚠️ Billing failed (node still succeeded): {billing_err}")
            
            new_output = result.get("output")
            
            # Build the set of fields to persist in MongoDB
            set_fields: Dict[str, Any] = {
                f"execution.node_states.{node_id}.status": "completed",
                f"execution.node_states.{node_id}.completed_at": completed_at,
                f"execution.outputs.{node_id}": new_output,
                f"outputs.{node_id}": new_output,
                "execution.status": "completed",
                "updated_at": datetime.now(timezone.utc),
            }
            
            # For videoGen nodes, also store extracted frames under special keys so
            # the frontend can auto-fill connected imageGen nodes without an extra run.
            start_frame = result.get("start_frame")
            end_frame = result.get("end_frame")
            if start_frame:
                set_fields[f"outputs.{node_id}__start_frame"] = start_frame
                set_fields[f"execution.outputs.{node_id}__start_frame"] = start_frame
            if end_frame:
                set_fields[f"outputs.{node_id}__end_frame"] = end_frame
                set_fields[f"execution.outputs.{node_id}__end_frame"] = end_frame
            
            # Use dot notation to update specific fields directly
            await collection.update_one(
                {"_id": oid},
                {"$set": set_fields}
            )
            
            # Register asset in persistent user_assets collection
            if new_output and isinstance(new_output, str) and _is_media_url(new_output):
                try:
                    from app.api.endpoints.user_assets import register_asset
                    wf_name = workflow.get("name", "Untitled Workflow")
                    await register_asset(
                        user_id=user_id,
                        workflow_id=workflow_id,
                        workflow_name=wf_name,
                        node_id=node_id,
                        node_type=node_type,
                        asset_url=new_output,
                        node_data=target_node.get("data"),
                    )
                except Exception as reg_err:
                    print(f"[NodeAsync] ⚠️ Asset registration failed: {reg_err}")
            
            print(f"[NodeAsync] Node {node_id} completed successfully")
        else:
            error_msg = result.get("error", "Unknown error")
            await collection.update_one(
                {"_id": oid},
                {"$set": {
                    f"execution.node_states.{node_id}.status": "failed",
                    f"execution.node_states.{node_id}.completed_at": completed_at,
                    f"execution.node_states.{node_id}.error": error_msg,
                    "execution.status": "failed",
                }}
            )
            print(f"[NodeAsync] Node {node_id} failed: {error_msg}")
            
    except Exception as e:
        error_msg = str(e)
        completed_at = datetime.now(timezone.utc).isoformat()
        
        await collection.update_one(
            {"_id": oid},
            {"$set": {
                f"execution.node_states.{node_id}.status": "failed",
                f"execution.node_states.{node_id}.completed_at": completed_at,
                f"execution.node_states.{node_id}.error": error_msg,
                "execution.status": "failed",
            }}
        )
        print(f"[NodeAsync] Node {node_id} exception: {e}")
    finally:
        reset_context(ctx_token)

async def _execute_workflow_async(workflow_id: str, run_id: str):
    """
    Background task: execute all nodes in topological order,
    updating per-node status in MongoDB so the frontend can poll.
    """
    collection = get_workflows_collection()
    oid = ObjectId(workflow_id)
    
    workflow = await collection.find_one({"_id": oid})
    if not workflow:
        return
    
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    execution_order = get_topological_order(nodes, edges)
    total = len(execution_order)
    
    # Initialize all node states as "queued"
    node_states = {}
    for nid in execution_order:
        node = next((n for n in nodes if n["id"] == nid), None)
        if node:
            node_states[nid] = {
                "status": "queued",
                "type": node.get("type"),
            }
    
    # Save initial execution state
    await collection.update_one(
        {"_id": oid},
        {"$set": {
            "execution": {
                "run_id": run_id,
                "status": "running",
                "node_states": node_states,
                "outputs": {},
                "errors": [],
                "progress": {"current": 0, "total": total},
            }
        }}
    )
    
    runner = NodeRunner()
    outputs: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []
    current = 0
    user_id = workflow.get("user_id")
    action_type_map = {
        "imageGen": ActionType.IMAGE_GEN,
        "videoGen": ActionType.VIDEO_GEN,
        "audioGen": ActionType.AUDIO_GEN,
        "editorAgent": ActionType.RENDER,
    }
    
    for node_id in execution_order:
        node = next((n for n in nodes if n["id"] == node_id), None)
        if not node:
            continue
        
        # Mark node as "running"
        now = datetime.now(timezone.utc).isoformat()
        node_states[node_id]["status"] = "running"
        node_states[node_id]["started_at"] = now
        
        await collection.update_one(
            {"_id": oid},
            {"$set": {
                f"execution.node_states.{node_id}.status": "running",
                f"execution.node_states.{node_id}.started_at": now,
                "execution.progress.current": current,
            }}
        )
        
        print(f"[WorkflowAsync] Running node: {node_id} (type: {node.get('type')})")
        
        try:
            result = await runner.run_node(
                node=node,
                nodes=nodes,
                edges=edges,
                outputs=outputs,
            )
            
            completed_at = datetime.now(timezone.utc).isoformat()
            
            if result.get("success"):
                outputs[node_id] = result.get("output")
                node_states[node_id]["status"] = "completed"
                node_states[node_id]["completed_at"] = completed_at
                
                # Billing
                cost = result.get("cost", 0.0)
                node_type = node.get("type")
                if node_type in action_type_map and cost > 0:
                    try:
                        billing_service = BillingService(get_database())
                        node_data = node.get("data", {})
                        meta = {"workflow_id": workflow_id, "node_id": node_id, "node_type": node_type}
                        if node_type == "imageGen":
                            meta["ratio"] = node_data.get("ratio", "1:1")
                        elif node_type == "videoGen":
                            meta["resolution"] = node_data.get("resolution", "720p")
                            meta["duration"] = node_data.get("duration", "4s")
                        if "prompt" in node_data:
                            meta["prompt"] = node_data["prompt"]

                        await billing_service.charge_usage(
                            user_id=user_id,
                            action=action_type_map[node_type],
                            cost_usd=cost,
                            model_name=result.get("model", node_type),
                            provider=result.get("provider", "fal.ai"),
                            metadata=meta,
                        )
                        print(f"[WorkflowAsync] ✅ Billed ${cost:.4f} for {node_type}")
                    except Exception as billing_err:
                        print(f"[WorkflowAsync] ⚠️ Billing failed: {billing_err}")
                
                await collection.update_one(
                    {"_id": oid},
                    {"$set": {
                        f"execution.node_states.{node_id}.status": "completed",
                        f"execution.node_states.{node_id}.completed_at": completed_at,
                        f"execution.outputs.{node_id}": result.get("output"),
                    }}
                )
            else:
                error_msg = result.get("error", "Unknown error")
                errors.append({"node_id": node_id, "error": error_msg})
                node_states[node_id]["status"] = "failed"
                node_states[node_id]["completed_at"] = completed_at
                node_states[node_id]["error"] = error_msg
                
                await collection.update_one(
                    {"_id": oid},
                    {"$set": {
                        f"execution.node_states.{node_id}.status": "failed",
                        f"execution.node_states.{node_id}.completed_at": completed_at,
                        f"execution.node_states.{node_id}.error": error_msg,
                    },
                    "$push": {
                        "execution.errors": {"node_id": node_id, "error": error_msg},
                    }}
                )
                
        except Exception as e:
            error_msg = str(e)
            completed_at = datetime.now(timezone.utc).isoformat()
            errors.append({"node_id": node_id, "error": error_msg})
            node_states[node_id]["status"] = "failed"
            node_states[node_id]["error"] = error_msg
            
            await collection.update_one(
                {"_id": oid},
                {"$set": {
                    f"execution.node_states.{node_id}.status": "failed",
                    f"execution.node_states.{node_id}.completed_at": completed_at,
                    f"execution.node_states.{node_id}.error": error_msg,
                },
                "$push": {
                    "execution.errors": {"node_id": node_id, "error": error_msg},
                }}
            )
            
            print(f"[WorkflowAsync] Node {node_id} exception: {e}")
        
        current += 1
    
    # Mark workflow execution as completed or failed
    final_status = "failed" if errors else "completed"
    
    await collection.update_one(
        {"_id": oid},
        {"$set": {
            "execution.status": final_status,
            "execution.progress.current": total,
            "outputs": outputs,
            "updated_at": datetime.now(timezone.utc),
        }}
    )
    
    print(f"[WorkflowAsync] Workflow {workflow_id} {final_status}. "
          f"Outputs: {len(outputs)}, Errors: {len(errors)}")


@router.post("/{workflow_id}/run-async", response_model=RunWorkflowAsyncResponse)
async def run_workflow_async(workflow_id: str, current_user: dict = Depends(get_current_user)):
    """Start async workflow execution. Poll /run-status for progress."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    user_id = current_user.get("_id")
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if already running
    execution = workflow.get("execution", {})
    if execution.get("status") == "running":
        return RunWorkflowAsyncResponse(
            run_id=execution.get("run_id", ""),
            status="running",
        )
    
    # Generate run ID and launch background task
    run_id = str(uuid4())
    
    print(f"[WorkflowAsync] Starting async run: {workflow_id} (run_id: {run_id})")
    
    asyncio.create_task(_execute_workflow_async(workflow_id, run_id))
    
    return RunWorkflowAsyncResponse(run_id=run_id, status="running")


@router.post("/{workflow_id}/nodes/{node_id}/run-async", response_model=RunWorkflowAsyncResponse)
async def run_node_async(
    workflow_id: str, 
    node_id: str, 
    request: RunNodeRequest = None,
    current_user: dict = Depends(get_current_user)
):
    """Start async node execution. Poll /{workflow_id}/run-status for progress on the given node."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    user_id = current_user.get("_id")
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
        
    execution = workflow.get("execution", {})
    node_state = execution.get("node_states", {}).get(node_id, {})
    
    if node_state.get("status") == "running":
        return RunWorkflowAsyncResponse(
            run_id=execution.get("run_id", ""), # reuse existing if available but not strictly matched
            status="running",
        )
    
    run_id = str(uuid4())
    print(f"[NodeAsync] Starting async node run: {workflow_id} / {node_id} (run_id: {run_id})")
    
    # Initialize execution.node_states for this node if execution doesn't exist
    if not execution:
        await collection.update_one(
            {"_id": oid},
            {"$set": {"execution": {"node_states": {}}}}
        )
        
    # Set it to queued
    await collection.update_one(
        {"_id": oid},
        {"$set": {
            f"execution.node_states.{node_id}": {
                "status": "queued",
                "type": next((n.get("type") for n in workflow.get("nodes", []) if n["id"] == node_id), "unknown"),
            },
            "updated_at": datetime.now(timezone.utc),
        }}
    )
    
    invoked = await _invoke_node_lambda(
        workflow_id=workflow_id,
        node_id=node_id,
        run_id=run_id,
        input_overrides=request.input_overrides if request else None,
    )
    
    if not invoked:
        # If the Lambda self-invoke failed, mark as failed so it doesn't get stuck in 'queued'
        await collection.update_one(
            {"_id": oid},
            {"$set": {
                f"execution.node_states.{node_id}.status": "failed",
                f"execution.node_states.{node_id}.error": "Failed to dispatch background execution.",
                "execution.status": "failed",
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        return RunWorkflowAsyncResponse(run_id=run_id, status="failed")

    return RunWorkflowAsyncResponse(run_id=run_id, status="running")


# ── Internal background execution endpoint (called by Lambda self-invoke) ─────

class BackgroundExecuteRequest(BaseModel):
    workflow_id: str
    node_id: str
    run_id: str
    input_overrides: Optional[Dict[str, Any]] = None
    invoke_secret: str = ""


@router.post("/execute-background")
async def execute_node_background(request: BackgroundExecuteRequest):
    """
    Internal endpoint: called by Lambda self-invocation (InvocationType=Event).
    Runs a single node synchronously within this Lambda's 15-min window.
    NOT intended to be called directly from the frontend.
    """
    expected_secret = os.environ.get("LAMBDA_INVOKE_SECRET", "kureita-internal")
    if request.invoke_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    print(f"[Background] ▶ execute-background START: workflow={request.workflow_id}, node={request.node_id}, run_id={request.run_id}")

    # Run the full node execution synchronously (we ARE the background Lambda)
    await _execute_node_async(
        workflow_id=request.workflow_id,
        node_id=request.node_id,
        run_id=request.run_id,
        input_overrides=request.input_overrides,
    )

    print(f"[Background] ✅ execute-background DONE: node={request.node_id}")
    return {"ok": True}


@router.get("/{workflow_id}/run-status", response_model=WorkflowRunStatus)
async def get_run_status(workflow_id: str, current_user: dict = Depends(get_current_user)):
    """Poll the current execution status of an async workflow run."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    user_id = current_user.get("_id")
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    execution = workflow.get("execution", {})
    
    if not execution:
        raise HTTPException(status_code=404, detail="No active run found. Start one with POST /run-async")
    
    # Self-heal single-node runs whose webhook was dropped: for any running node
    # with a pending fal request_id, opportunistically poll fal and finalize if done.
    await _sweep_stale_node_run_states(workflow_id=str(oid), execution=execution)
    workflow = await collection.find_one({"_id": oid}) or workflow
    execution = workflow.get("execution", {}) or execution

    # Build node states from stored data
    raw_states = execution.get("node_states", {})
    node_states = {}
    
    for nid, state in raw_states.items():
        if state.get("status") == "running" and state.get("started_at"):
            try:
                started = datetime.fromisoformat(state["started_at"])
                if datetime.now(timezone.utc) - started > timedelta(minutes=15):
                    await collection.update_one(
                        {"_id": oid},
                        {"$set": {
                            f"execution.node_states.{nid}.status": "failed",
                            f"execution.node_states.{nid}.error": "Timed out — Lambda may have been recycled. Please retry.",
                            "execution.status": "failed",
                        }}
                    )
                    state["status"] = "failed"
                    state["error"] = "Timed out. Please retry."
                    execution["status"] = "failed"
            except Exception:
                pass

        node_states[nid] = NodeState(
            status=state.get("status", "queued"),
            started_at=state.get("started_at"),
            completed_at=state.get("completed_at"),
            error=state.get("error"),
        )
    
    return WorkflowRunStatus(
        run_id=execution.get("run_id", ""),
        status=execution.get("status", "running"),
        node_states=node_states,
        outputs=presign_urls(execution.get("outputs", {})),
        errors=execution.get("errors", []),
        progress=execution.get("progress", {}),
    )


# ============================================
# Presigned URL Refresh Endpoint
# ============================================

class PresignRequest(BaseModel):
    urls: List[str]


@router.post("/presign")
async def presign_urls_endpoint(
    request: PresignRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate fresh presigned URLs for S3 keys. Used by frontend to refresh expired URLs."""
    from app.services.storage_service import S3StorageService
    s3_service = S3StorageService()
    
    result = {}
    for url in request.urls:
        if S3StorageService.is_s3_url(url):
            result[url] = s3_service.get_presigned_url(url)
        else:
            result[url] = url
    
    return {"urls": result}


@router.post("/cleanup-urls")
async def cleanup_presigned_urls(current_user: dict = Depends(get_current_user)):
    """One-time cleanup: strip presigned URL params from all stored data in MongoDB.
    
    This fixes existing data where presigned URLs were accidentally persisted.
    Safe to run multiple times (idempotent).
    """
    collection = get_workflows_collection()
    
    user_id = current_user.get("_id")
    query = {"$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]}
    cursor = collection.find(query)
    workflows = await cursor.to_list(length=1000)
    
    cleaned_count = 0
    for w in workflows:
        oid = w["_id"]
        
        # Clean outputs
        outputs = w.get("outputs", {})
        clean_outputs = strip_presigned_from_data(outputs)
        
        # Clean node data (specifically data.output fields)
        nodes = w.get("nodes", [])
        clean_nodes = strip_presigned_from_data(nodes)
        
        # Check if anything changed
        if clean_outputs != outputs or clean_nodes != nodes:
            await collection.update_one(
                {"_id": oid},
                {"$set": {
                    "outputs": clean_outputs,
                    "nodes": clean_nodes,
                }}
            )
            cleaned_count += 1
            print(f"[Cleanup] Cleaned presigned URLs in workflow {oid}")

    print(f"[Cleanup] Done. Cleaned {cleaned_count}/{len(workflows)} workflows.")
    return {"cleaned": cleaned_count, "total": len(workflows)}

class ForkWorkflowResponse(BaseModel):
    id: str
    name: str
    forked_from: str


@router.post("/{workflow_id}/fork", response_model=ForkWorkflowResponse)
async def fork_workflow(workflow_id: str, current_user: dict = Depends(get_current_user)):
    """Fork (clone) a public workflow into the current user's account."""
    collection = get_workflows_collection()

    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")

    # First check if user already owns this workflow
    user_id = current_user.get("_id")
    own_workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}],
    })

    if own_workflow:
        # User already owns it, just return the existing ID
        return ForkWorkflowResponse(
            id=str(own_workflow["_id"]),
            name=own_workflow.get("name", "Untitled Workflow"),
            forked_from=workflow_id,
        )

    # Otherwise, look for it as a public workflow
    source = await collection.find_one({"_id": oid, "is_public": True})
    if not source:
        raise HTTPException(status_code=404, detail="Workflow not found or is not public")

    now = datetime.now(timezone.utc)
    fork_data = {
        "name": source.get("name", "Untitled Workflow"),
        "user_id": user_id,
        "nodes": source.get("nodes", []),
        "edges": source.get("edges", []),
        "outputs": source.get("outputs", {}),
        "chat_history": [],
        "forked_from": workflow_id,
        "created_at": now,
        "updated_at": now,
    }

    result = await collection.insert_one(fork_data)
    new_id = str(result.inserted_id)

    print(f"[Workflow] Forked {workflow_id} → {new_id} for user {user_id}")

    return ForkWorkflowResponse(
        id=new_id,
        name=fork_data["name"],
        forked_from=workflow_id,
    )


class TogglePublicRequest(BaseModel):
    is_public: bool


@router.post("/{workflow_id}/toggle-public")
async def toggle_workflow_public(
    workflow_id: str,
    request: TogglePublicRequest,
    current_user: dict = Depends(get_current_user),
):
    """Toggle the public visibility of a workflow."""
    collection = get_workflows_collection()

    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")

    user_id = current_user.get("_id")
    query = {
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}],
    }

    result = await collection.update_one(
        query,
        {"$set": {"is_public": request.is_public, "updated_at": datetime.now(timezone.utc)}},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")

    print(f"[Workflow] Set is_public={request.is_public} for workflow {workflow_id}")
    return {"success": True, "is_public": request.is_public}


class UploadRenderPresignRequest(BaseModel):
    filename: str
    content_type: str = "video/mp4"

@router.post("/{workflow_id}/nodes/{node_id}/upload-render/presign")
async def get_upload_render_presigned_url(
    workflow_id: str,
    node_id: str,
    request: UploadRenderPresignRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a presigned URL to upload a client-rendered video blob directly to S3.
    This bypasses AWS API Gateway's 10MB payload size limit.
    """
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")

    collection = get_workflows_collection()
    user_id = current_user.get("_id")

    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    from app.services.storage_service import S3StorageService, LocalStorageService
    # Use LocalStorageService if configured without S3
    from app.core.dependencies import get_storage_service
    storage = get_storage_service()

    safe_filename = f"editor_render_{workflow_id}_{node_id}_{int(datetime.now().timestamp())}.mp4"
    return storage.generate_presigned_upload_url(safe_filename, request.content_type)


class ConfirmUploadRequest(BaseModel):
    file_url: str


def _extract_render_frames(file_url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract start/end frames from a rendered editor video when possible."""
    try:
        from app.services.storage_service import S3StorageService

        runner = NodeRunner()
        source_url = file_url

        if S3StorageService().is_s3_url(file_url):
            source_url = S3StorageService().get_presigned_url(file_url)

        start_frame = runner._extract_video_frame(source_url, "start_frame")
        end_frame = runner._extract_video_frame(source_url, "end_frame")
        return start_frame, end_frame
    except Exception as err:
        print(f"[Workflow] Editor render frame extraction failed: {err}")
        return None, None


@router.post("/{workflow_id}/nodes/{node_id}/upload-render/confirm")
async def confirm_upload_render(
    workflow_id: str,
    node_id: str,
    request: ConfirmUploadRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Confirm that the client has successfully uploaded a rendered video to S3 
    using the presigned URL, and save the resulting URL to the workflow's database outputs.
    """
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")

    collection = get_workflows_collection()
    user_id = current_user.get("_id")

    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    from app.services.storage_service import S3StorageService
    file_url = S3StorageService.strip_presigned_params(request.file_url)
    start_frame, end_frame = _extract_render_frames(file_url)

    set_fields: Dict[str, Any] = {
            f"outputs.{node_id}": file_url,
            f"execution.outputs.{node_id}": file_url,
            "updated_at": datetime.now(timezone.utc)
    }
    if start_frame:
        set_fields[f"outputs.{node_id}__start_frame"] = start_frame
        set_fields[f"execution.outputs.{node_id}__start_frame"] = start_frame
    if end_frame:
        set_fields[f"outputs.{node_id}__end_frame"] = end_frame
        set_fields[f"execution.outputs.{node_id}__end_frame"] = end_frame

    await collection.update_one(
        {"_id": oid},
        {"$set": set_fields}
    )

    storage = S3StorageService()
    return {"url": file_url, "presigned_url": storage.get_presigned_url(file_url)}


@router.post("/{workflow_id}/nodes/{node_id}/upload-render")
async def upload_rendered_video(
    workflow_id: str,
    node_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Legacy and local-fallback endpoint for the frontend to upload a client-rendered video blob.
    """
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")

    collection = get_workflows_collection()
    user_id = current_user.get("_id")

    # Verify workflow ownership
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}]
    })

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    from app.core.dependencies import get_storage_service
    storage = get_storage_service()
    
    # Upload to S3 (or local)
    filename = f"editor_render_{workflow_id}_{node_id}_{int(datetime.now().timestamp())}.mp4"
    print(f"[{workflow_id}/{node_id}] Uploading rendered video locally as {filename}")

    try:
        file_bytes = await file.read()
        file_url = await storage.upload_file(file_bytes, filename, content_type="video/mp4")
        
        from app.services.storage_service import S3StorageService
        file_url = S3StorageService.strip_presigned_params(file_url)
        start_frame, end_frame = _extract_render_frames(file_url)

        set_fields: Dict[str, Any] = {
                f"outputs.{node_id}": file_url,
                f"execution.outputs.{node_id}": file_url,
                "updated_at": datetime.now(timezone.utc)
        }
        if start_frame:
            set_fields[f"outputs.{node_id}__start_frame"] = start_frame
            set_fields[f"execution.outputs.{node_id}__start_frame"] = start_frame
        if end_frame:
            set_fields[f"outputs.{node_id}__end_frame"] = end_frame
            set_fields[f"execution.outputs.{node_id}__end_frame"] = end_frame

        await collection.update_one(
            {"_id": oid},
            {"$set": set_fields}
        )

        return {"url": file_url, "presigned_url": storage.get_presigned_url(file_url)}

    except Exception as e:
        print(f"Error uploading rendered video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Run-All Job Orchestration
# ============================================
NON_EXECUTABLE_TYPES = {"comment"}
SKIP_IF_HAS_DATA_TYPES = {"text", "upload", "mediaUpload"}

@router.post("/{workflow_id}/jobs", response_model=CreateJobResponse)
async def create_job(workflow_id: str, current_user: dict = Depends(get_current_user)):
    """Create a Run-All job: topological sort, build task list, kick off processor."""
    collection = get_workflows_collection()
    jobs_collection = get_workflow_jobs_collection()

    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")

    user_id = current_user.get("_id")
    workflow = await collection.find_one({
        "_id": oid,
        "$or": [{"user_id": user_id}, {"user_id": {"$exists": False}}],
    })
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Reject if a job is already running for this workflow
    existing = await jobs_collection.find_one({
        "workflow_id": workflow_id,
        "status": {"$in": ["pending", "running"]},
    })
    if existing:
        return CreateJobResponse(job_id=existing["id"], status=existing["status"])

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    outputs = workflow.get("outputs", {})
    execution_order = get_topological_order(nodes, edges)
    node_map = {n["id"]: n for n in nodes}

    tasks: List[Dict[str, Any]] = []
    for nid in execution_order:
        node = node_map.get(nid)
        if not node:
            continue
        ntype = node.get("type", "unknown")

        if ntype in NON_EXECUTABLE_TYPES:
            tasks.append(JobTask(node_id=nid, node_type=ntype, status="skipped").model_dump())
            continue

        if ntype in SKIP_IF_HAS_DATA_TYPES:
            has_output = bool(outputs.get(nid))
            has_data = bool(node.get("data", {}).get("text")) or bool(node.get("data", {}).get("url"))
            if has_output or has_data:
                tasks.append(JobTask(node_id=nid, node_type=ntype, status="skipped").model_dump())
                continue

        if outputs.get(nid):
            tasks.append(JobTask(node_id=nid, node_type=ntype, status="skipped").model_dump())
            continue

        tasks.append(JobTask(node_id=nid, node_type=ntype, status="pending").model_dump())

    job_id = str(uuid4())
    run_id = str(uuid4())
    now = datetime.now(timezone.utc)

    job_doc = {
        "id": job_id,
        "workflow_id": workflow_id,
        "user_id": user_id,
        "run_id": run_id,
        "tasks": tasks,
        "status": "running",
        "current_task_index": 0,
        "total_tasks": len(tasks),
        "heartbeat_at": now,
        "max_retries": 2,
        "skip_completed": True,
        "stop_on_failure": True,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "outputs": {},
        "errors": [],
    }
    await jobs_collection.insert_one(job_doc)

    print(f"[RunAll] Created job {job_id} for workflow {workflow_id}: {len(tasks)} tasks")

    await _invoke_job_processor_lambda(job_id)

    return CreateJobResponse(job_id=job_id, status="running")

@router.get("/{workflow_id}/jobs/active", response_model=Optional[JobStatusResponse])
async def get_active_job(workflow_id: str, current_user: dict = Depends(get_current_user)):
    """Return the currently running job for this workflow (for page reload recovery)."""
    jobs_collection = get_workflow_jobs_collection()
    job = await jobs_collection.find_one({
        "workflow_id": workflow_id,
        "status": {"$in": ["pending", "running"]},
    })
    if not job:
        return None
    return _serialize_job_status(job)

@router.get("/{workflow_id}/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(workflow_id: str, job_id: str, current_user: dict = Depends(get_current_user)):
    """Poll job progress.

    Also acts as a missed-webhook sweeper: if any task is stuck in `waiting_webhook`
    for > 90s, we opportunistically poll fal.ai for status and finalize the task
    locally. This self-heals jobs when a webhook is dropped without requiring a
    dedicated scheduler.
    """
    jobs_collection = get_workflow_jobs_collection()
    job = await jobs_collection.find_one({"id": job_id, "workflow_id": workflow_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await _sweep_stale_webhook_tasks(job)
    job = await jobs_collection.find_one({"id": job_id, "workflow_id": workflow_id}) or job
    return _serialize_job_status(job)


async def _sweep_stale_webhook_tasks(job: dict) -> None:
    """Opportunistically poll fal.ai for any task stuck in waiting_webhook > 90s."""
    tasks = job.get("tasks") or []
    stale_cutoff_s = 90
    now = datetime.now(timezone.utc)

    stale_request_ids: List[str] = []
    for task in tasks:
        if task.get("status") != "waiting_webhook":
            continue
        started_at_str = task.get("started_at")
        try:
            started_at = datetime.fromisoformat(started_at_str) if started_at_str else None
        except Exception:
            started_at = None
        if started_at and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if not started_at or (now - started_at).total_seconds() < stale_cutoff_s:
            continue
        rid = task.get("fal_request_id")
        if rid:
            stale_request_ids.append(rid)

    if not stale_request_ids:
        return

    print(
        f"[Sweeper] job={job.get('id')} found {len(stale_request_ids)} "
        f"stale waiting_webhook task(s) — polling fal"
    )

    fal_jobs = get_fal_jobs_collection()
    from app.services.fal_service import FalService
    from app.api.endpoints.fal_webhook import process_fal_callback

    fal_service = FalService()
    for rid in stale_request_ids:
        fal_job = await fal_jobs.find_one({"request_id": rid})
        if not fal_job or fal_job.get("status") in ("completed", "failed"):
            continue
        endpoint = fal_job.get("endpoint_id")
        if not endpoint:
            continue
        try:
            poll = await fal_service.fetch_result(endpoint, rid)
        except Exception as e:
            print(f"[Sweeper] fal poll failed for {rid}: {e}")
            continue
        if poll["status"] == "COMPLETED":
            print(f"[Sweeper] self-healing request_id={rid}")
            await process_fal_callback(
                request_id=rid,
                status="OK",
                result=poll.get("output"),
                error_msg=None,
            )
        elif poll["status"] == "UNKNOWN" and poll.get("error"):
            # fal reports an unrecoverable error for this request.
            await process_fal_callback(
                request_id=rid,
                status="ERROR",
                result=None,
                error_msg=poll.get("error"),
            )

async def _sweep_stale_node_run_states(*, workflow_id: str, execution: dict) -> None:
    """Poll fal for any single-node run stuck in webhook-pending state > 90s.

    Mirrors `_sweep_stale_webhook_tasks` but for single-node async runs, which
    store `fal_request_id`/`fal_endpoint_id` on `execution.node_states.{node_id}`
    instead of on a `workflow_jobs` task.
    """
    raw_states = execution.get("node_states", {}) or {}
    stale_cutoff_s = 90
    now = datetime.now(timezone.utc)

    candidates: List[tuple[str, str, str]] = []  # (node_id, request_id, endpoint_id)
    for nid, state in raw_states.items():
        if state.get("status") != "running":
            continue
        rid = state.get("fal_request_id")
        endpoint = state.get("fal_endpoint_id")
        if not rid or not endpoint:
            continue
        started_at_str = state.get("started_at")
        try:
            started_at = datetime.fromisoformat(started_at_str) if started_at_str else None
        except Exception:
            started_at = None
        if started_at and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if not started_at or (now - started_at).total_seconds() < stale_cutoff_s:
            continue
        candidates.append((nid, rid, endpoint))

    if not candidates:
        return

    print(
        f"[NodeSweeper] workflow={workflow_id} found {len(candidates)} stale "
        f"single-node run(s) — polling fal"
    )

    from app.services.fal_service import FalService
    from app.api.endpoints.fal_webhook import process_fal_callback

    fal_service = FalService()
    fal_jobs = get_fal_jobs_collection()
    for _node_id, rid, endpoint in candidates:
        fal_job = await fal_jobs.find_one({"request_id": rid})
        if fal_job and fal_job.get("status") in ("completed", "failed"):
            continue
        try:
            poll = await fal_service.fetch_result(endpoint, rid)
        except Exception as e:
            print(f"[NodeSweeper] fal poll failed for {rid}: {e}")
            continue
        if poll["status"] == "COMPLETED":
            print(f"[NodeSweeper] self-healing request_id={rid}")
            await process_fal_callback(
                request_id=rid, status="OK",
                result=poll.get("output"), error_msg=None,
            )
        elif poll["status"] == "UNKNOWN" and poll.get("error"):
            await process_fal_callback(
                request_id=rid, status="ERROR",
                result=None, error_msg=poll.get("error"),
            )


@router.post("/{workflow_id}/jobs/{job_id}/cancel")
async def cancel_job(workflow_id: str, job_id: str, current_user: dict = Depends(get_current_user)):
    """Cancel a running job. Current node finishes, rest are skipped."""
    jobs_collection = get_workflow_jobs_collection()
    result = await jobs_collection.update_one(
        {"id": job_id, "workflow_id": workflow_id, "status": {"$in": ["pending", "running"]}},
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="No active job found to cancel")
    print(f"[RunAll] Job {job_id} cancelled")
    return {"ok": True}

@router.post("/{workflow_id}/jobs/{job_id}/nudge")
async def nudge_job(workflow_id: str, job_id: str, current_user: dict = Depends(get_current_user)):
    """Client-assisted heartbeat: re-invoke processor if a job appears stuck."""
    jobs_collection = get_workflow_jobs_collection()
    job = await jobs_collection.find_one({"id": job_id, "workflow_id": workflow_id})
    if not job or job["status"] not in ("pending", "running"):
        raise HTTPException(status_code=404, detail="No active job to nudge")

    heartbeat = job.get("heartbeat_at")
    if heartbeat and isinstance(heartbeat, datetime):
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
        if heartbeat > stale_threshold:
            return {"ok": True, "message": "Job heartbeat is recent, no nudge needed"}

    # Reset any stuck running task back to pending
    tasks = job.get("tasks", [])
    updated = False
    for task in tasks:
        if task["status"] == "running":
            task["status"] = "pending"
            task["attempt"] = task.get("attempt", 0) + 1
            updated = True
    if updated:
        await jobs_collection.update_one(
            {"id": job_id},
            {"$set": {"tasks": tasks, "updated_at": datetime.now(timezone.utc)}},
        )

    await _invoke_job_processor_lambda(job_id)
    print(f"[RunAll] Job {job_id} nudged — processor re-invoked")
    return {"ok": True, "message": "Processor re-invoked"}


def _serialize_job_status(job: dict) -> JobStatusResponse:
    """Convert a MongoDB job doc to a JobStatusResponse, presigning output URLs."""
    tasks = [
        JobTaskStatus(
            node_id=t["node_id"],
            node_type=t["node_type"],
            status=t["status"],
            attempt=t.get("attempt", 0),
            started_at=t.get("started_at"),
            completed_at=t.get("completed_at"),
            error=t.get("error"),
        )
        for t in job.get("tasks", [])
    ]
    raw_outputs = job.get("outputs", {})
    presigned = presign_urls(raw_outputs)
    return JobStatusResponse(
        job_id=job["id"],
        status=job["status"],
        current_task_index=job.get("current_task_index", 0),
        total_tasks=job.get("total_tasks", 0),
        tasks=tasks,
        outputs=presigned,
        errors=job.get("errors", []),
    )

# ── Job Processor (Lambda self-invoke target) ────────────────────────────────
async def _invoke_job_processor_lambda(job_id: str) -> bool:
    """Fire-and-forget: invoke this Lambda to process the next task in a job."""
    function_name = _get_lambda_function_name()

    if not function_name:
        print(f"[RunAll] Local mode — using asyncio.create_task for job {job_id}")
        task = asyncio.create_task(_process_job(job_id))
        _running_tasks.add(task)
        task.add_done_callback(_running_tasks.discard)
        return True

    payload = {
        "job_id": job_id,
        "invoke_secret": os.environ.get("LAMBDA_INVOKE_SECRET", "kureita-internal"),
    }

    api_gw_event = {
        "version": "2.0",
        "routeKey": "POST /api/workflows/job-processor",
        "rawPath": "/api/workflows/job-processor",
        "rawQueryString": "",
        "headers": {
            "content-type": "application/json",
            "x-invoke-source": "lambda-self",
        },
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/api/workflows/job-processor",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "lambda-self-invoke",
            },
            "accountId": os.environ.get("AWS_ACCOUNT_ID", ""),
            "requestId": job_id,
            "stage": "$default",
            "apiId": "self",
        },
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }

    try:
        import boto3
        lambda_client = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(api_gw_event).encode("utf-8"),
        )
        status = response.get("StatusCode")
        print(f"[RunAll] Lambda self-invoke dispatched for job {job_id} — status: {status}")
        return status == 202
    except Exception as e:
        print(f"[RunAll] Lambda self-invoke failed for job {job_id}: {e}")
        task = asyncio.create_task(_process_job(job_id))
        _running_tasks.add(task)
        task.add_done_callback(_running_tasks.discard)
        return False


async def _process_job(job_id: str):
    """
    Core job processor: execute one pending task, persist results, chain to next.
    Each Lambda invocation handles exactly one node.
    """
    jobs_collection = get_workflow_jobs_collection()
    wf_collection = get_workflows_collection()

    job = await jobs_collection.find_one({"id": job_id})
    if not job:
        print(f"[RunAll] Job {job_id} not found — aborting")
        return

    # ── Guard checks ──
    if job["status"] in ("cancelled", "completed", "failed"):
        print(f"[RunAll] Job {job_id} is {job['status']} — stopping")
        return

    tasks = job.get("tasks", [])
    workflow_id = job["workflow_id"]
    user_id = job["user_id"]

    # Find next pending task
    pending_tasks = [(i, t) for i, t in enumerate(tasks) if t["status"] == "pending"]

    if not pending_tasks:
        # All done
        now = datetime.now(timezone.utc)
        has_errors = len(job.get("errors", [])) > 0
        final_status = "failed" if has_errors else "completed"
        await jobs_collection.update_one(
            {"id": job_id},
            {"$set": {
                "status": final_status,
                "completed_at": now,
                "updated_at": now,
            }},
        )
        # Copy accumulated outputs to the workflow document
        if job.get("outputs"):
            try:
                wf_oid = ObjectId(workflow_id)
                await wf_collection.update_one(
                    {"_id": wf_oid},
                    {"$set": {
                        **{f"outputs.{k}": v for k, v in job["outputs"].items()},
                        "updated_at": now,
                    }},
                )
            except Exception as e:
                print(f"[RunAll] Failed to copy outputs to workflow: {e}")
        print(f"[RunAll] Job {job_id} {final_status} ({len(tasks)} tasks)")
        return

    task_index, task = pending_tasks[0]
    node_id = task["node_id"]
    node_type = task["node_type"]
    now_iso = datetime.now(timezone.utc).isoformat()

    print(f"[RunAll] Job {job_id} — processing task {task_index}/{len(tasks)}: {node_id} ({node_type})")

    # Update heartbeat + mark task running
    await jobs_collection.update_one(
        {"id": job_id},
        {"$set": {
            f"tasks.{task_index}.status": "running",
            f"tasks.{task_index}.started_at": now_iso,
            "current_task_index": task_index,
            "heartbeat_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    # Load fresh workflow data (outputs may have changed from previous tasks)
    try:
        wf_oid = ObjectId(workflow_id)
    except Exception:
        await fail_task(jobs_collection, job_id, task_index, "Invalid workflow ID")
        return

    workflow = await wf_collection.find_one({"_id": wf_oid})
    if not workflow:
        await fail_task(jobs_collection, job_id, task_index, "Workflow not found")
        return

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    outputs = workflow.get("outputs", {})

    target_node = next((n for n in nodes if n["id"] == node_id), None)
    if not target_node:
        await fail_task(jobs_collection, job_id, task_index, f"Node {node_id} not found in workflow")
        return


    # ── Execute the node ──
    runner = NodeRunner()
    action_type_map = {
        "imageGen": ActionType.IMAGE_GEN,
        "videoGen": ActionType.VIDEO_GEN,
        "audioGen": ActionType.AUDIO_GEN,
        "editorAgent": ActionType.RENDER,
    }

    ctx_token = set_context({
        "job_id": job_id,
        "task_index": task_index,
        "node_id": node_id,
        "node_type": node_type,
        "user_id": str(user_id) if user_id else "",
        "workflow_id": workflow_id,
    })
    try:
        result = await runner.run_node(
            node=target_node,
            nodes=nodes,
            edges=edges,
            outputs=outputs,
        )

        completed_at = datetime.now(timezone.utc).isoformat()

        # ── Webhook path: job enqueued on fal, finalize in webhook handler ──
        if result.get("success") and result.get("status") == "pending_fal":
            await jobs_collection.update_one(
                {"id": job_id},
                {"$set": {
                    f"tasks.{task_index}.status": "waiting_webhook",
                    f"tasks.{task_index}.fal_request_id": result.get("request_id"),
                    f"tasks.{task_index}.fal_endpoint_id": result.get("endpoint_id"),
                    "heartbeat_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            print(f"[RunAll] Task {node_id} deferred to webhook (request_id={result.get('request_id')})")
            return

        if result.get("success"):
            # ── Billing ──
            cost = result.get("cost", 0.0)
            if node_type in action_type_map and cost > 0:
                try:
                    billing_service = BillingService(get_database())
                    node_data = target_node.get("data", {})
                    meta = {"workflow_id": workflow_id, "node_id": node_id, "node_type": node_type}
                    if node_type == "imageGen":
                        meta["ratio"] = node_data.get("ratio", "1:1")
                    elif node_type == "videoGen":
                        meta["resolution"] = node_data.get("resolution", "720p")
                        meta["duration"] = node_data.get("duration", "4s")
                    if "prompt" in node_data:
                        meta["prompt"] = node_data["prompt"]
                    await billing_service.charge_usage(
                        user_id=user_id,
                        action=action_type_map[node_type],
                        cost_usd=cost,
                        model_name=result.get("model", node_type),
                        provider=result.get("provider", "fal.ai"),
                        metadata=meta,
                    )
                    print(f"[RunAll] Billed ${cost:.4f} for {node_type}")
                except Exception as billing_err:
                    print(f"[RunAll] Billing failed (node succeeded): {billing_err}")

            new_output = result.get("output")

            # Persist to job doc
            set_fields: Dict[str, Any] = {
                f"tasks.{task_index}.status": "completed",
                f"tasks.{task_index}.completed_at": completed_at,
                f"outputs.{node_id}": new_output,
                "updated_at": datetime.now(timezone.utc),
                "heartbeat_at": datetime.now(timezone.utc),
            }

            start_frame = result.get("start_frame")
            end_frame = result.get("end_frame")
            if start_frame:
                set_fields[f"outputs.{node_id}__start_frame"] = start_frame
            if end_frame:
                set_fields[f"outputs.{node_id}__end_frame"] = end_frame

            await jobs_collection.update_one({"id": job_id}, {"$set": set_fields})

            # Also persist to workflow.outputs so the next node's _resolve_inputs() sees it
            wf_set: Dict[str, Any] = {
                f"outputs.{node_id}": new_output,
                "updated_at": datetime.now(timezone.utc),
            }
            if start_frame:
                wf_set[f"outputs.{node_id}__start_frame"] = start_frame
            if end_frame:
                wf_set[f"outputs.{node_id}__end_frame"] = end_frame
            await wf_collection.update_one({"_id": wf_oid}, {"$set": wf_set})

            # Register asset in persistent user_assets collection
            if new_output and isinstance(new_output, str) and _is_media_url(new_output):
                try:
                    from app.api.endpoints.user_assets import register_asset
                    wf_name = workflow.get("name", "Untitled Workflow")
                    await register_asset(
                        user_id=user_id,
                        workflow_id=workflow_id,
                        workflow_name=wf_name,
                        node_id=node_id,
                        node_type=node_type,
                        asset_url=new_output,
                        node_data=target_node.get("data"),
                    )
                except Exception as reg_err:
                    print(f"[RunAll] ⚠️ Asset registration failed: {reg_err}")

            print(f"[RunAll] Task {node_id} completed")

        else:
            error_msg = result.get("error", "Unknown error")
            attempt = task.get("attempt", 0)
            max_retries = job.get("max_retries", 2)

            if attempt < max_retries:
                # Retry: reset to pending with incremented attempt
                await jobs_collection.update_one(
                    {"id": job_id},
                    {"$set": {
                        f"tasks.{task_index}.status": "pending",
                        f"tasks.{task_index}.attempt": attempt + 1,
                        f"tasks.{task_index}.error": error_msg,
                        "heartbeat_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }},
                )
                print(f"[RunAll] Task {node_id} failed (attempt {attempt + 1}/{max_retries}), retrying")
            else:
                await jobs_collection.update_one(
                    {"id": job_id},
                    {"$set": {
                        f"tasks.{task_index}.status": "failed",
                        f"tasks.{task_index}.completed_at": completed_at,
                        f"tasks.{task_index}.error": error_msg,
                        "heartbeat_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$push": {
                        "errors": {"node_id": node_id, "error": error_msg, "attempt": attempt},
                    }},
                )
                print(f"[RunAll] Task {node_id} failed permanently: {error_msg}")

                if job.get("stop_on_failure", True):
                    await jobs_collection.update_one(
                        {"id": job_id},
                        {"$set": {"status": "failed", "updated_at": datetime.now(timezone.utc)}},
                    )
                    print(f"[RunAll] Job {job_id} stopped due to failure (stop_on_failure=True)")
                    return


    except Exception as e:
        error_msg = str(e)
        completed_at = datetime.now(timezone.utc).isoformat()
        attempt = task.get("attempt", 0)
        max_retries = job.get("max_retries", 2)

        if attempt < max_retries:
            await jobs_collection.update_one(
                {"id": job_id},
                {"$set": {
                    f"tasks.{task_index}.status": "pending",
                    f"tasks.{task_index}.attempt": attempt + 1,
                    f"tasks.{task_index}.error": error_msg,
                    "heartbeat_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            print(f"[RunAll] Task {node_id} exception (attempt {attempt + 1}/{max_retries}), retrying: {e}")
        else:
            await jobs_collection.update_one(
                {"id": job_id},
                {"$set": {
                    f"tasks.{task_index}.status": "failed",
                    f"tasks.{task_index}.completed_at": completed_at,
                    f"tasks.{task_index}.error": error_msg,
                    "heartbeat_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
                "$push": {
                    "errors": {"node_id": node_id, "error": error_msg, "attempt": attempt},
                }},
            )
            print(f"[RunAll] Task {node_id} exception (final): {e}")

            if job.get("stop_on_failure", True):
                await jobs_collection.update_one(
                    {"id": job_id},
                    {"$set": {"status": "failed", "updated_at": datetime.now(timezone.utc)}},
                )
                print(f"[RunAll] Job {job_id} stopped due to exception")
                return
    finally:
        reset_context(ctx_token)

    # ── Chain: invoke next task ──
    await _invoke_job_processor_lambda(job_id)


async def fail_task(jobs_collection, job_id: str, task_index: int, error: str):
    """Mark a task as failed and stop the job."""
    now = datetime.now(timezone.utc)
    await jobs_collection.update_one(
        {"id": job_id},
        {"$set": {
            f"tasks.{task_index}.status": "failed",
            f"tasks.{task_index}.completed_at": now.isoformat(),
            f"tasks.{task_index}.error": error,
            "status": "failed",
            "updated_at": now,
        },
        "$push": {
            "errors": {"node_id": f"task{task_index}", "error": error},
        }},
    )
    print(f"[RunAll] Task {task_index} hard-failed: {error}")

async def job_processor_background(request: JobProcessorRequest):
    """Internal endpoint: Lambda self-invocation target for job processing."""
    expected_secret = os.environ.get("LAMBDA_INVOKE_SECRET", "kureita-internal")
    if request.invoke_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    print(f"[RunAll] job-processor invoked for job {request.job_id}")
    await _process_job(request.job_id)
    print(f"[RunAll] job-processor done for job {request.job_id}")
    return {"ok": True}
