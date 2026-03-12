from typing import Dict, Any, List, Optional
import os
import json
import asyncio
import boto3
import ulid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.services.agent_service import AgentService
from app.services.billing import BillingService
from app.models.usage import ActionType
from app.core.database import get_database
from app.core.auth import get_current_user
from app.models.agent_job import AgentJob, AgentJobStatus, AgentJobResponse, AgentJobStatusResponse

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

async def process_agent_flow(job_id: str, user_id: str, db: AsyncIOMotorDatabase, billing_service: BillingService, agent_svc: AgentService):
    # Mark as processing
    await db["agent_jobs"].update_one(
        {"id": job_id},
        {"$set": {"status": AgentJobStatus.PROCESSING, "updated_at": datetime.now(timezone.utc)}}
    )
    
    job_data = await db["agent_jobs"].find_one({"id": job_id})
    if not job_data:
        return
        
    try:
        result = await agent_svc.generate_workflow(
            prompt=job_data["prompt"],
            model=job_data["model"],
            current_nodes=job_data.get("current_nodes", []),
            current_edges=job_data.get("current_edges", []),
            chat_history=job_data.get("chat_history", [])
        )
        
        # Billing — use actual cost from OpenRouter
        if result.get("success"):
            cost_usd = result.get("cost_usd", 0.0)
            token_usage = result.get("token_usage", {"input": 0, "output": 0})
            total_tokens = token_usage.get("input", 0) + token_usage.get("output", 0)
            
            if cost_usd > 0:
                await billing_service.charge_usage(
                    user_id=user_id,
                    action=ActionType.AI_CHAT,
                    cost_usd=cost_usd,
                    model_name=job_data.get("model", "LLM"),
                    provider="OpenRouter",
                    tokens_used=total_tokens,
                    metadata={"prompt": job_data["prompt"][:50] + "..." if len(job_data["prompt"]) > 50 else job_data["prompt"]},
                )

        # Update job
        await db["agent_jobs"].update_one(
            {"id": job_id},
            {"$set": {
                "status": AgentJobStatus.COMPLETED if result.get("success") else AgentJobStatus.FAILED,
                "success": result.get("success"),
                "message": result.get("message"),
                "thinking": result.get("thinking"),
                "thinking_duration_ms": result.get("thinking_duration_ms"),
                "tool_calls": result.get("tool_calls"),
                "nodes": result.get("nodes"),
                "edges": result.get("edges"),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
    except Exception as e:
        await db["agent_jobs"].update_one(
            {"id": job_id},
            {"$set": {
                "status": AgentJobStatus.FAILED,
                "error": str(e),
                "updated_at": datetime.now(timezone.utc)
            }}
        )


@router.post("/flow", response_model=AgentJobResponse)
async def generate_flow(
    request: GenerateFlowRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    billing_service: BillingService = Depends(get_billing_service)
):
    """
    Generate a workflow structure asynchronously. Returns job_id for polling.
    """
    user_id = current_user["auth0_sub"]

    # 1. Pre-check: Ensure user has positive balance
    current_balance = await billing_service.get_user_balance(user_id)
    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    job_id = ulid.new().str
    
    # 2. Save job to DB
    job_doc = AgentJob(
        id=job_id,
        user_id=user_id,
        prompt=request.prompt,
        model=request.model,
        current_nodes=request.current_nodes,
        current_edges=request.current_edges,
        chat_history=request.chat_history
    ).model_dump()
    
    await db["agent_jobs"].insert_one(job_doc)
    
    # 3. Trigger background
    token = req.headers.get("authorization", "")
    
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'ap-south-1'))
        event = {
            "version": "2.0",
            "rawPath": "/api/agent/internal/flow-worker",
            "requestContext": {
                "http": {
                    "method": "POST",
                    "path": "/api/agent/internal/flow-worker"
                }
            },
            "headers": {
                "content-type": "application/json",
                "authorization": token
            },
            "body": json.dumps({"job_id": job_id, "user_id": user_id})
        }
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: client.invoke(
            FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],
            InvocationType='Event',
            Payload=json.dumps(event)
        ))
    else:
        background_tasks.add_task(process_agent_flow, job_id, user_id, db, billing_service, agent_service)
        
    return AgentJobResponse(job_id=job_id, status=AgentJobStatus.PENDING)

class FlowWorkerRequest(BaseModel):
    job_id: str
    user_id: str

@router.post("/internal/flow-worker")
async def flow_worker(
    request: FlowWorkerRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    billing_service: BillingService = Depends(get_billing_service)
):
    if current_user["auth0_sub"] != request.user_id:
        raise HTTPException(status_code=403, detail="User mismatch")
    
    await process_agent_flow(request.job_id, request.user_id, db, billing_service, agent_service)
    return {"status": "ok"}

@router.get("/flow/status/{job_id}", response_model=AgentJobStatusResponse)
async def get_flow_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    job_data = await db["agent_jobs"].find_one({"id": job_id, "user_id": current_user["auth0_sub"]})
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
        
    status = job_data["status"]
    
    if status in [AgentJobStatus.COMPLETED, AgentJobStatus.FAILED]:
        return AgentJobStatusResponse(
            job_id=job_id,
            status=status,
            result={
                "success": job_data.get("success", False),
                "message": job_data.get("message") or job_data.get("error"),
                "thinking": job_data.get("thinking"),
                "thinking_duration_ms": job_data.get("thinking_duration_ms"),
                "tool_calls": job_data.get("tool_calls", []),
                "nodes": job_data.get("nodes", []),
                "edges": job_data.get("edges", []),
            },
            error=job_data.get("error")
        )
    
    return AgentJobStatusResponse(job_id=job_id, status=status)
