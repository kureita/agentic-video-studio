"""Workflow CRUD and Execution Endpoints."""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.database import get_database
from app.core.auth import get_current_user
from app.services.node_runner import NodeRunner

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


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None
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
    # Let the router handle presigning output URLs if necessary
    return {
        "id": str(workflow.get("_id")) if "_id" in workflow else workflow.get("id"),
        "name": workflow.get("name", "Untitled Workflow"),
        "nodes": nodes,
        "edges": edges,
        "outputs": workflow.get("outputs", {}),
        "chat_history": chat_history,
        "created_at": workflow.get("created_at", datetime.now(timezone.utc)).isoformat(),
        "updated_at": workflow.get("updated_at", datetime.now(timezone.utc)).isoformat(),
    }
    
import re

def presign_urls(data: Any, s3_service=None) -> Any:
    """Helper to recursively presign all s3 url strings in an object.
    
    Handles both raw S3 URLs and already-presigned URLs (strips old signature first).
    """
    if s3_service is None:
        from app.services.storage_service import S3StorageService
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
            # If it's a markdown string, extract URLs and replace them
            pattern = r'(https://[^"\s\'\>\)]*kureita[^"\s\'\>\)]*amazonaws\.com[^"\s\'\>\)]+)'
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
    
    now = datetime.now(timezone.utc)
    workflow_data = {
        "name": request.name or "Untitled Workflow",
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
                updated_at=w.get("updated_at", datetime.now(timezone.utc)).isoformat(),
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
        update_data["chat_history"] = [msg.model_dump() for msg in request.chat_history]
    
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
    
    print(f"[Workflow] Running node: {node_id} (type: {target_node.get('type')})")
    
    # Run the node
    runner = NodeRunner()
    result = await runner.run_node(
        node=target_node,
        nodes=nodes,
        edges=edges,
        outputs=outputs,
        input_overrides=request.input_overrides if request else None,
    )
    
    if result.get("success"):
        # Update outputs in database
        # First, get the current outputs object
        workflow = await collection.find_one({"_id": oid})
        current_outputs = workflow.get("outputs", {})
        current_outputs[node_id] = result.get("output")
        
        # Update the entire outputs object to avoid creating separate fields
        await collection.update_one(
            {"_id": oid},
            {"$set": {"outputs": current_outputs, "updated_at": datetime.now(timezone.utc)}}
        )
        
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
    )


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
    
    # Build node states from stored data
    raw_states = execution.get("node_states", {})
    node_states = {}
    for nid, state in raw_states.items():
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

