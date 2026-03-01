from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.services.agent_service import AgentService
from app.services.billing import BillingService
from app.models.usage import ActionType
from app.core.database import get_database

from app.core.auth import get_current_user

router = APIRouter()
agent_service = AgentService()

def get_billing_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> BillingService:
    return BillingService(db)

class GenerateFlowRequest(BaseModel):
    prompt: str
    model: str = "Gemini 2.5 Flash"
    current_nodes: Optional[List[Dict[str, Any]]] = []
    current_edges: Optional[List[Dict[str, Any]]] = []
    chat_history: Optional[List[Dict[str, Any]]] = []

class ToolCall(BaseModel):
    name: str
    status: str = "completed"  # "running", "completed", "failed"
    args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None

class GenerateFlowResponse(BaseModel):
    success: bool
    message: str
    thinking: Optional[str] = None
    thinking_duration_ms: Optional[int] = None
    tool_calls: Optional[List[ToolCall]] = []
    nodes: Optional[List[Dict[str, Any]]] = []
    edges: Optional[List[Dict[str, Any]]] = []

@router.post("/flow", response_model=GenerateFlowResponse)
async def generate_flow(
    request: GenerateFlowRequest,
    current_user: dict = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """
    Generate a workflow structure based on a text prompt.
    """
    user_id = current_user["auth0_sub"]

    # 1. Pre-check: Ensure user has positive balance before initiating expensive AI call
    current_balance = await billing_service.get_user_balance(user_id)
    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # 2. Invoke the Agent Service LLM
    result = await agent_service.generate_workflow(
        prompt=request.prompt,
        model=request.model,
        current_nodes=request.current_nodes,
        current_edges=request.current_edges,
        chat_history=request.chat_history,
    )
    
    # 3. Post-execution Billing: Deduct proportionally based on actual tracked tokens only on success
    if result.get("success"):
        token_usage = result.get("token_usage", {"input": 0, "output": 0})
        total_tokens = token_usage.get("input", 0) + token_usage.get("output", 0)
        
        await billing_service.deduct_credits(
            user_id=user_id,
            action=ActionType.AI_CHAT,
            tokens_used=total_tokens,
            metadata={"prompt": request.prompt[:50] + "..." if len(request.prompt) > 50 else request.prompt}
        )
        
    return result
