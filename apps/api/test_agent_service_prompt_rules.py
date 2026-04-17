import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.agent_service import AgentService


def _mock_openrouter_response(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(payload),
                    tool_calls=[],
                )
            )
        ],
        usage=None,
    )


@pytest.mark.asyncio
async def test_workflow_prompt_separates_start_frame_and_video_text_rules() -> None:
    service = AgentService()
    service._resolve_chat_model_config = AsyncMock(
        return_value={
            "display_name": "Test Model",
            "openrouter_model": "openrouter/test-model",
            "input_modalities": ["text"],
        }
    )

    create = AsyncMock(
        return_value=_mock_openrouter_response(
            {
                "thinking": "plan",
                "message": "ok",
                "nodes": [],
                "edges": [],
            }
        )
    )
    service.openrouter_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=create,
            )
        )
    )

    result = await service.generate_workflow(
        prompt="Build a workflow with a generated start frame and a video clip for each scene.",
        model="Test Model",
    )

    assert result["success"] is True

    start_prompt = create.await_args.kwargs["messages"][1]["content"]

    assert (
        "If a scene includes BOTH a generated `imageGen` start frame and a `videoGen` clip, "
        "you MUST create TWO separate text nodes for that scene:"
        in start_prompt
    )
    assert (
        "Do NOT connect the same text node to both the scene's `imageGen` and `videoGen` "
        "when a start frame is being generated."
        in start_prompt
    )
    assert "### 7A. Start-Frame Text Node Template" in start_prompt
    assert "### 7B. Video Motion Text Node Template" in start_prompt
    assert (
        "Start-Frame Text (x=0) -> Start Image (x=700) -> Motion Text (x=1400) -> Video (x=2100)"
        in start_prompt
    )
