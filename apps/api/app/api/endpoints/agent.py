"""Agent Endpoints - Workflow generation and chat."""

import json
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.agent_service import AgentService
from app.services.agent_orchestrator import (
    get_orchestrator,
    ChatMessage,
    WorkflowState,
    AgentResponse,
)

router = APIRouter()
agent_service = AgentService()


# ============================================
# Legacy Flow Generation (kept for compatibility)
# ============================================

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
    (Legacy endpoint - kept for backward compatibility)
    """
    result = await agent_service.generate_workflow(
        prompt=request.prompt,
        current_nodes=request.current_nodes,
        current_edges=request.current_edges
    )
    
    return result


# ============================================
# New Chat-based Agent API
# ============================================

class ChatMessageInput(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""
    messages: List[ChatMessageInput]
    workflow: Optional[WorkflowState] = None
    model: str = "openai"  # "openai" | "claude" | "gemini"


class ChatResponse(BaseModel):
    """Non-streaming response from chat endpoint."""
    intent: str
    thinking: str
    message: str
    actions: List[Dict[str, Any]] = []


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message and return workflow actions.
    
    This is the non-streaming version. Use /chat/stream for real-time updates.
    """
    orchestrator = get_orchestrator(provider=request.model)
    
    messages = [
        ChatMessage(role=m.role, content=m.content)
        for m in request.messages
    ]
    
    response = await orchestrator.process(
        messages=messages,
        workflow=request.workflow,
    )
    
    return ChatResponse(
        intent=response.intent,
        thinking=response.thinking,
        message=response.message,
        actions=[action.model_dump() for action in response.actions],
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Process a chat message with Server-Sent Events (SSE) streaming.
    
    Returns a stream of events:
    - status: Current processing status
    - thinking: Agent's reasoning
    - action: Individual workflow action
    - message: Final user-facing message
    - complete: Full response data
    - error: Error message if something went wrong
    """
    orchestrator = get_orchestrator(provider=request.model)
    
    messages = [
        ChatMessage(role=m.role, content=m.content)
        for m in request.messages
    ]
    
    async def event_generator():
        """Generate SSE events."""
        async for event in orchestrator.process_stream(
            messages=messages,
            workflow=request.workflow,
        ):
            # Format as SSE
            event_type = event.get("type", "message")
            event_data = event.get("data", "")
            
            # JSON encode the data
            if isinstance(event_data, (dict, list)):
                data_str = json.dumps(event_data)
            else:
                data_str = str(event_data)
            
            yield f"event: {event_type}\ndata: {data_str}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
