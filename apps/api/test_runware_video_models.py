import pytest

from app.core.model_registry import get_model_by_id, resolve_air_id
from app.services.runware_service import RunwareService


def test_video_model_registry_matches_current_runware_ids() -> None:
    assert resolve_air_id("sora-2-pro", "fallback", model_type="video") == "openai:3@2"
    assert resolve_air_id("openai:sora@2-pro", "fallback", model_type="video") == "openai:3@2"
    assert resolve_air_id("vidu:q@3", "fallback", model_type="video") == "vidu:4@1"
    assert resolve_air_id("vidu:q@3-turbo", "fallback", model_type="video") == "vidu:4@2"

    grok = get_model_by_id("grok-imagine-video")
    assert grok is not None
    assert grok["reference_images_max"] == 7
    assert set(grok["input_modes"]) == {"t2v", "i2v", "reference", "v2v"}


def test_resolution_specific_duration_resolution_logic() -> None:
    service = RunwareService()

    assert service._resolve_dimensions("google:3@2", "16:9", "4k") == (3840, 2160)  # type: ignore[attr-defined]
    assert service._resolve_duration(  # type: ignore[attr-defined]
        "lightricks:ltx@2.3-fast",
        17,
        resolution="1080p",
    ) == 18
    assert service._resolve_duration(  # type: ignore[attr-defined]
        "lightricks:ltx@2.3-fast",
        17,
        resolution="4k",
    ) == 10
    assert service._resolve_duration("pixverse:1@7", 10, resolution="1080p") == 8  # type: ignore[attr-defined]
    assert service._resolve_duration("pixverse:1@7", 10, resolution="540p") == 10  # type: ignore[attr-defined]
    assert service._resolve_duration("minimax:4@1", 10, resolution="1080p") == 6  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_generate_video_uses_vidu_audio_patch_and_requested_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunwareService()
    captured: dict[str, object] = {}

    async def fake_post(tasks: list[dict[str, object]]) -> dict[str, object]:
        captured["task"] = tasks[0]
        return {
            "success": True,
            "data": {"videoURL": "https://example.com/video.mp4", "cost": 0.0},
        }

    monkeypatch.setattr(service, "_post", fake_post)

    result = await service.generate_video(
        prompt="A runner crossing a rainy neon street",
        model="vidu:4@1",
        duration=7,
        resolution="1080p",
        aspect_ratio="16:9",
        generate_audio=False,
    )

    assert result["success"] is True
    task = captured["task"]
    assert isinstance(task, dict)
    assert task["width"] == 1920
    assert task["height"] == 1080
    assert task["duration"] == 7
    assert task["providerSettings"] == {"vidu": {"audio": False}}


@pytest.mark.asyncio
async def test_image_to_video_uses_provider_specific_frame_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunwareService()
    uploads = iter(["start-frame-uuid", "end-frame-uuid"])
    captured: dict[str, dict[str, object]] = {}

    async def fake_url_to_data_uri(url: str) -> str:
        return f"data:image/png;base64,{url.split('/')[-1]}"

    async def fake_upload_image_to_runware(_image_data: str) -> str:
        return next(uploads)

    async def fake_post(tasks: list[dict[str, object]]) -> dict[str, object]:
        captured["task"] = tasks[0]
        return {
            "success": True,
            "data": {"videoURL": "https://example.com/video.mp4", "cost": 0.0},
        }

    monkeypatch.setattr(service, "_url_to_data_uri", fake_url_to_data_uri)
    monkeypatch.setattr(service, "_upload_image_to_runware", fake_upload_image_to_runware)
    monkeypatch.setattr(service, "_post", fake_post)

    pixverse_result = await service.image_to_video(
        image_url="https://example.com/start.png",
        prompt="Animate this illustration into a short reveal shot",
        model="pixverse:1@7",
        duration=10,
        resolution="1080p",
        aspect_ratio="16:9",
        end_image_url="https://example.com/end.png",
        generate_audio=True,
    )

    assert pixverse_result["success"] is True
    pixverse_task = captured["task"]
    assert pixverse_task["duration"] == 8
    assert pixverse_task["providerSettings"] == {"pixverse": {"audio": True}}
    assert pixverse_task["inputs"] == {
        "frameImages": [
            {"inputImage": "start-frame-uuid", "frame": "first"},
            {"inputImage": "end-frame-uuid", "frame": "last"},
        ]
    }

    captured.clear()
    uploads = iter(["openai-start-uuid", "openai-end-uuid"])
    monkeypatch.setattr(service, "_upload_image_to_runware", fake_upload_image_to_runware)

    sora_result = await service.image_to_video(
        image_url="https://example.com/start.png",
        prompt="Animate this frame into a cinematic scene",
        model="openai:3@2",
        duration=9,
        resolution="1080p",
        aspect_ratio="16:9",
        end_image_url="https://example.com/end.png",
        generate_audio=False,
    )

    assert sora_result["success"] is True
    sora_task = captured["task"]
    assert sora_task["duration"] == 12
    assert sora_task["inputs"] == {
        "frameImages": [
            {"image": "openai-start-uuid", "frame": "first"},
        ]
    }
    assert "providerSettings" not in sora_task
