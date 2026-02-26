import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.image_generator import ImageGenerator

async def main():
    print("Testing ImageGenerator with 'Kling Image' model name (should fallback to FLUX)...")
    gen = ImageGenerator()
    
    result = await gen.generate_image(
        prompt="A red apple on a white table, product photography",
        aspect_ratio="9:16",
        style="realistic",
        model_name="Kling Image",  # This is the model name from the frontend
    )
    
    if result.get("success"):
        print(f"✅ Success! Image URL: {result.get('image_url')}")
    else:
        print(f"❌ Failed: {result.get('error')}")

asyncio.run(main())
