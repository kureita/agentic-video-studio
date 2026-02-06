from typing import Literal
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from app.agents.director import DirectorAgent
from app.models.graph import GraphPlan

router = APIRouter()
director = DirectorAgent()


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class PlanRequest(BaseModel):
    messages: list[Message]
    model: Literal["openai", "anthropic", "gemini"] = "openai"

@router.post("/plan", response_model=GraphPlan)
async def create_workflow_plan(request: PlanRequest):
    """
    Generate a workflow graph based on the chat history.
    """
    try:
        # Convert Pydantic models to dicts for the agent
        msgs = [{"role": m.role, "content": m.content} for m in request.messages]
        plan = await director.create_plan(msgs, request.model)
        return plan
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[API] Director Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate workflow plan")
