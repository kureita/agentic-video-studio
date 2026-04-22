"""Contextvar plumbing so generators know when they're executing inside a
workflow task and therefore can legitimately defer to the fal webhook.

When `fal_webhook_context` is set (i.e. `_process_job` is running a node),
fal-backed generators submit asynchronously and return `pending_fal`.
When it is not set (canvas.py, generate.py, pipeline.py, chat tools, etc.),
the generators run synchronously via `fal_client.subscribe`.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional, TypedDict


class FalWebhookContext(TypedDict, total=False):
    # Run-All job mode (job_id + task_index set)
    job_id: str
    task_index: int
    # Single-node async run mode (run_id set, job_id absent)
    run_id: str
    # Common fields — always populated
    node_id: str
    node_type: str
    user_id: str
    workflow_id: str


fal_webhook_context: ContextVar[Optional[FalWebhookContext]] = ContextVar(
    "fal_webhook_context", default=None
)


def current_context() -> Optional[FalWebhookContext]:
    return fal_webhook_context.get()


def set_context(ctx: Optional[FalWebhookContext]) -> Any:
    """Set the context and return the token (reset with `reset_context(token)`)."""
    return fal_webhook_context.set(ctx)


def reset_context(token: Any) -> None:
    fal_webhook_context.reset(token)
