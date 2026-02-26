import sys
import os
import asyncio

# Ensure app directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.runware_service import RunwareService
from app.core.config import settings

async def main():
    print(f"Testing Runware Integration...")
    
    if not settings.runware_api_key:
        print("❌ Error: RUNWARE_API_KEY is not set in .env.local")
        return
        
    print(f"API Key found: {settings.runware_api_key[:4]}...{settings.runware_api_key[-4:] if len(settings.runware_api_key) > 8 else ''}")
    
    # Initialize service
    runware = RunwareService()
    
    print("\n--- Testing Image Generation (Tiny 64x64) ---")
    try:
        # Keep dimensions tiny to make generation extremely fast and cheap
        result = await runware.generate_image(
            prompt="A tiny test icon of a happy star",
            width=512, # Runware often requires min 512
            height=512,
            model="runware:101@1" # Flux Schnell
        )
        
        if result.get("success"):
            print(f"✅ Success! Image URL: {result.get('image_url')}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            if "details" in result:
                print(f"   Details: {result['details']}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
