from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    name: str
    status: str = "completed"
    args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None

class AgentJobStatus(str):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentJob(BaseModel):
    id: str = Field(..., description="Unique identifier for the job")
    user_id: str
    status: str = AgentJobStatus.PENDING
    prompt: str
    model: str
    current_nodes: Optional[List[Dict[str, Any]]] = []
    current_edges: Optional[List[Dict[str, Any]]] = []
    chat_history: Optional[List[Dict[str, Any]]] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Result fields
    success: Optional[bool] = None
    message: Optional[str] = None
    thinking: Optional[str] = None
    thinking_duration_ms: Optional[int] = None
    tool_calls: Optional[List[ToolCall]] = []
    nodes: Optional[List[Dict[str, Any]]] = []
    edges: Optional[List[Dict[str, Any]]] = []
    
    # Error fields
    error: Optional[str] = None

class AgentJobResponse(BaseModel):
    job_id: str
    status: str
    
class AgentJobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    
