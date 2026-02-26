import asyncio
import os
from dotenv import load_dotenv
load_dotenv(".env.local")

from app.services.runware_service import RunwareService

async def main():
    service = RunwareService()
    print("Testing image to video...")
    import base64
    from PIL import Image
    from io import BytesIO
    
    img = Image.new("RGB", (512, 512), color="red")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_data = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    
    try:
        resp = await service.image_to_video(
            image_url=img_data,
            prompt="a test video",
            model="klingai:kling-video@3-standard",
            duration=5
        )
        print("Final response:", resp)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
