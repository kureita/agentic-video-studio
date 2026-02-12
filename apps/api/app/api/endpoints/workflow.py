"""Workflow CRUD and Execution Endpoints."""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import get_database
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


# ============================================
# CRUD Endpoints
# ============================================

@router.post("", response_model=WorkflowResponse)
async def create_workflow(request: CreateWorkflowRequest):
    """Create a new workflow."""
    collection = get_workflows_collection()
    
    now = datetime.now(timezone.utc)
    workflow_data = {
        "name": request.name or "Untitled Workflow",
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
    
    return serialize_workflow(workflow_data)


@router.get("", response_model=List[WorkflowListItem])
async def list_workflows():
    """List all workflows."""
    collection = get_workflows_collection()
    
    cursor = collection.find({}).sort("updated_at", -1)
    workflows = await cursor.to_list(length=100)
    
    return [
        WorkflowListItem(
            id=str(w["_id"]),
            name=w.get("name", "Untitled Workflow"),
            updated_at=w.get("updated_at", datetime.now(timezone.utc)).isoformat(),
            node_count=len(w.get("nodes", [])),
            nodes=[
                {"id": n.get("id"), "type": n.get("type"), "position": n.get("position", {})}
                for n in w.get("nodes", [])
            ],
            edges=[
                {"id": e.get("id"), "source": e.get("source"), "target": e.get("target")}
                for e in w.get("edges", [])
            ],
        )
        for w in workflows
    ]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str):
    """Get a workflow by ID."""
    collection = get_workflows_collection()
    
    try:
        workflow = await collection.find_one({"_id": ObjectId(workflow_id)})
    except Exception as e:
        print(f"[Workflow] Invalid workflow ID: {workflow_id}, error: {e}")
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    if not workflow:
        print(f"[Workflow] Workflow not found: {workflow_id}")
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    serialized = serialize_workflow(workflow)
    print(f"[Workflow] Retrieved workflow {workflow_id}: {len(serialized['nodes'])} nodes, {len(serialized['edges'])} edges")
    
    return serialized


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, request: UpdateWorkflowRequest):
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
        update_data["nodes"] = [node.model_dump() for node in request.nodes]
    if request.edges is not None:
        update_data["edges"] = [edge.model_dump() for edge in request.edges]
    if request.chat_history is not None:
        update_data["chat_history"] = [msg.model_dump() for msg in request.chat_history]
    
    result = await collection.update_one(
        {"_id": oid},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Return updated workflow
    workflow = await collection.find_one({"_id": oid})
    
    print(f"[Workflow] Updated workflow: {workflow_id}")
    
    return serialize_workflow(workflow)


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    result = await collection.delete_one({"_id": oid})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    print(f"[Workflow] Deleted workflow: {workflow_id}")
    
    return {"success": True, "message": "Workflow deleted"}


# ============================================
# Execution Endpoints
# ============================================

@router.post("/{workflow_id}/nodes/{node_id}/run", response_model=RunNodeResponse)
async def run_node(workflow_id: str, node_id: str, request: RunNodeRequest = None):
    """Run a single node in a workflow."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    workflow = await collection.find_one({"_id": oid})
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
    
    return RunNodeResponse(
        success=result.get("success", False),
        node_id=node_id,
        output=result.get("output"),
        error=result.get("error"),
    )


@router.post("/{workflow_id}/run", response_model=RunWorkflowResponse)
async def run_workflow(workflow_id: str):
    """Run the entire workflow by executing nodes in topological order."""
    collection = get_workflows_collection()
    
    try:
        oid = ObjectId(workflow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    workflow = await collection.find_one({"_id": oid})
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
    
    return RunWorkflowResponse(
        success=len(errors) == 0,
        outputs=outputs,
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
