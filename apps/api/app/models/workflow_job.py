from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class JobTask(BaseModel):
    node_id: str
    node_type: str
    status: str = "pending" # pending | running | completed | failed | skipped
    attempt: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

class WorkflowJob(BaseModel):
    id: str = Field(..., description="Unique job identifier (UUID)")
    workflow_id: str
    user_id: str
    run_id: str

    tasks: List[JobTask] = []

    status: str = "pending" # pending | running | completed | failed | cancelled
    current_task_index: int = 0
    total_tasks: int = 0

    heartbeat_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    max_retries: int = 2

    skip_completed: bool = True
    stop_on_failure: bool = True

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    outputs: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []

# -- API Response Models --

class CreateJobResponse(BaseModel):
    job_id: str
    status: str

class JobTaskStatus(BaseModel):
    node_id: str
    node_type: str
    status: str
    attempt: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_task_index: int
    total_tasks: int
    tasks: List[JobTaskStatus] = []
    outputs: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []

class JobProcessorRequest(BaseModel):
    job_id: str
    invoke_secret: str = ""