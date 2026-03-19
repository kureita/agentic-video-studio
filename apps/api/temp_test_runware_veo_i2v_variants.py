import asyncio
import copy
from typing import Dict, Any, List

from app.services.runware_service import RunwareService


IMAGE_URL = "https://picsum.photos/720/1280.jpg"
MODEL = "google:3@2"
PROMPT = "A cinematic close-up of floating particles and subtle camera motion"


def make_base_task() -> Dict[str, Any]:
    return {
        "taskType": "videoInference",
        "model": MODEL,
        "outputType": "URL",
        "outputFormat": "MP4",
        "positivePrompt": PROMPT,
        "duration": 4,
        "width": 720,
        "height": 1280,
    }


async def run() -> None:
    service = RunwareService()
    data_uri = await service._url_to_data_uri(IMAGE_URL)  # type: ignore[attr-defined]
    image_uuid = await service._upload_image_to_runware(data_uri)  # type: ignore[attr-defined]
    image_ref = image_uuid or data_uri

    variants: List[Dict[str, Any]] = []

    # Variant A: top-level referenceImages
    a = make_base_task()
    a["referenceImages"] = [image_ref]
    variants.append({"name": "top_referenceImages", "task": a})

    # Variant B: inputs.referenceImages
    b = make_base_task()
    b["inputs"] = {"referenceImages": [image_ref]}
    variants.append({"name": "inputs_referenceImages", "task": b})

    # Variant C: inputs.frameImages with image key
    c = make_base_task()
    c["inputs"] = {"frameImages": [{"image": image_ref, "frame": "first"}]}
    variants.append({"name": "inputs_frameImages_image", "task": c})

    # Variant D: top-level frameImages with inputImage key
    d = make_base_task()
    d["frameImages"] = [{"inputImage": image_ref, "frame": "first"}]
    variants.append({"name": "top_frameImages_inputImage", "task": d})

    # Variant E: top-level frameImages with image key
    e = make_base_task()
    e["frameImages"] = [{"image": image_ref, "frame": "first"}]
    variants.append({"name": "top_frameImages_image", "task": e})

    for variant in variants:
        task = copy.deepcopy(variant["task"])
        response = await service._post([task])  # type: ignore[attr-defined]
        print(f"\n[{variant['name']}] success={response.get('success')}")
        if response.get("success"):
            print("accepted_keys:", list(task.keys()))
            print("data_keys:", list((response.get("data") or {}).keys()))
            task_uuid = (response.get("data") or {}).get("taskUUID")
            if task_uuid and variant["name"] in ("inputs_frameImages_image", "top_frameImages_inputImage"):
                print(f"polling taskUUID={task_uuid} ...")
                poll = await service._poll_task_completion(task_uuid, max_attempts=20, delay=5)  # type: ignore[attr-defined]
                print("poll_success:", poll.get("success"))
                if not poll.get("success"):
                    print("poll_error:", poll.get("error"))
                else:
                    print("poll_data_keys:", list((poll.get("data") or {}).keys()))
        else:
            print("error:", response.get("error"))


if __name__ == "__main__":
    asyncio.run(run())
