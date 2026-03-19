import asyncio
from typing import Dict, Any, List

from app.services.runware_service import RunwareService


class DryRunRunwareService(RunwareService):
    def __init__(self):
        super().__init__()
        self.recorded_tasks: List[Dict[str, Any]] = []
        self.video_task_uuid = "dryrun-video-task-uuid"

    async def _post(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Record every task for payload assertions.
        self.recorded_tasks.extend(tasks)
        task = tasks[0]
        task_type = task.get("taskType")

        if task_type == "imageUpload":
            return {"success": True, "data": {"imageUUID": "dryrun-image-uuid"}}

        if task_type == "videoInference":
            return {"success": True, "data": {"taskUUID": self.video_task_uuid}}

        if task_type == "getResponse":
            return {"success": True, "data": {"status": "success", "videoURL": "https://example.com/dryrun.mp4"}}

        return {"success": False, "error": f"Unhandled dry-run task type: {task_type}"}

    async def _url_to_data_uri(self, url: str) -> str:
        # Keep deterministic, no network.
        return "data:image/jpeg;base64,DRYRUN"


async def main() -> None:
    svc = DryRunRunwareService()

    result = await svc.image_to_video(
        image_url="https://example.com/start.jpg",
        prompt="Animate subtle movement",
        model="google:3@2",
        duration=4,
        aspect_ratio="9:16",
        generate_audio=True,
    )

    assert result.get("success") is True, f"Expected success, got: {result}"
    assert result.get("video_url") == "https://example.com/dryrun.mp4"

    video_tasks = [t for t in svc.recorded_tasks if t.get("taskType") == "videoInference"]
    assert video_tasks, "Expected a videoInference task to be sent"
    video_task = video_tasks[0]

    # Critical assertions for the user-reported issue:
    assert video_task.get("inputs", {}).get("frameImages"), "Expected frameImages payload for Veo image-to-video"
    assert video_task.get("providerSettings", {}).get("google", {}).get("generateAudio") is True, "Expected native audio providerSettings for Veo"
    assert (video_task.get("width"), video_task.get("height")) == (720, 1280), "Expected 9:16 dimensions for Veo payload"

    print("Dry-run video node payload checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
