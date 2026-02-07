from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.agent_service import AgentService

router = APIRouter()
agent_service = AgentService()

class GenerateFlowRequest(BaseModel):
    prompt: str
    current_nodes: Optional[List[Dict[str, Any]]] = []
    current_edges: Optional[List[Dict[str, Any]]] = []

class GenerateFlowResponse(BaseModel):
    success: bool
    message: str
    nodes: Optional[List[Dict[str, Any]]] = []
    edges: Optional[List[Dict[str, Any]]] = []

@router.post("/flow", response_model=GenerateFlowResponse)
async def generate_flow(request: GenerateFlowRequest):
    """
    Generate a workflow structure based on a text prompt.
    """
    result = await agent_service.generate_workflow(
        prompt=request.prompt,
        current_nodes=request.current_nodes,
        current_edges=request.current_edges
    )
    
    return result
