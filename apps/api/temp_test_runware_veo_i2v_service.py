import asyncio

from app.services.runware_service import RunwareService


async def run() -> None:
    service = RunwareService()
    result = await service.image_to_video(
        image_url="https://picsum.photos/720/1280.jpg",
        prompt="Money bills and coins dissolving into glowing digital pixels",
        model="google:3@2",
        duration=4,
        aspect_ratio="9:16",
        generate_audio=True,
    )
    print("success:", result.get("success"))
    print("model:", result.get("model"))
    print("error:", result.get("error"))
    print("video_url:", (result.get("video_url") or "")[:120])

    if not result.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run())
