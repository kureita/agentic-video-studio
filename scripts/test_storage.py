import asyncio
import os
from dotenv import load_dotenv
from app.core.config import settings
from app.core.dependencies import get_storage_service

# Load env
load_dotenv(".env")

async def test_storage():
    print(f"Testing Storage Service (Type: {settings.storage_type})")
    
    storage = get_storage_service()
    print(f"Service Class: {type(storage).__name__}")
    
    # Test file
    content = b"Hello, Storage World!"
    filename = "test_storage_file.txt"
    content_type = "text/plain"
    
    try:
        # Upload
        print(f"Uploading {filename}...")
        url = await storage.upload_file(content, filename, content_type)
        print(f"✓ Uploaded: {url}")
        
        # Verify Local
        if settings.storage_type == "local":
            path = url.split("/static/")[-1]
            full_path = f"static/{path}"
            if os.path.exists(full_path):
                 print(f"✓ File exists locally: {full_path}")
            else:
                 print(f"✗ File not found locally: {full_path}")
                 
        # Delete (Optional, unimplemented in S3Storage for now?)
        # StorageService has delete_file abstract method
        print(f"Deleting {url}...")
        success = await storage.delete_file(url)
        if success:
            print("✓ Deleted")
        else:
            print("✗ Delete failed (or not implemented/supported)")
            
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_storage())
