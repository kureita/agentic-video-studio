import asyncio
from typing import Dict, Any, Optional

from app.services.runware_service import RunwareService


def _build_task(
    service: RunwareService,
    model: str,
    prompt: str,
    duration: int,
    aspect_ratio: str,
    generate_audio: bool,
) -> Dict[str, Any]:
    width, height = service._resolve_dimensions(model, aspect_ratio)  # type: ignore[attr-defined]
    if model.startswith("google:"):
        # Veo payload validation is strict; use known-safe dimensions.
        width, height = 1280, 720
    resolved_duration = service._resolve_duration(model, duration)  # type: ignore[attr-defined]
    provider_settings: Optional[Dict[str, Any]] = service._audio_provider_settings(model, generate_audio)  # type: ignore[attr-defined]

    task: Dict[str, Any] = {
        "taskType": "videoInference",
        "model": model,
        "outputType": "URL",
        "outputFormat": "MP4",
        "positivePrompt": prompt,
        "duration": resolved_duration,
        "width": width,
        "height": height,
    }
    if provider_settings:
        task["providerSettings"] = provider_settings
    return task


async def run() -> None:
    service = RunwareService()
    cases = [
        {"model": "google:3@2", "generate_audio": True, "label": "veo-native-audio-on"},
        {"model": "google:3@2", "generate_audio": False, "label": "veo-native-audio-off"},
        {"model": "klingai:kling-video@3-standard", "generate_audio": True, "label": "kling-audio-requested-no-provider-settings"},
    ]

    prompt = "A cinematic sunrise over calm ocean waves, realistic lighting, smooth camera move"

    failures = []
    for case in cases:
        task = _build_task(
            service=service,
            model=case["model"],
            prompt=prompt,
            duration=4,
            aspect_ratio="16:9",
            generate_audio=case["generate_audio"],
        )
        resp = await service._post([task])  # type: ignore[attr-defined]
        ok = bool(resp.get("success"))
        print(f"[{case['label']}] success={ok} model={case['model']} providerSettings={task.get('providerSettings')}")
        if not ok:
            failures.append({"case": case["label"], "error": resp.get("error")})

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"- {failure['case']}: {failure['error']}")
        raise SystemExit(1)

    print("\nAll Runware payload checks passed.")


if __name__ == "__main__":
    asyncio.run(run())
