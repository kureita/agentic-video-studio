import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load env from apps/api/.env - trying absolute path or relative from script run location
# When running from apps/api with `python ../../scripts/test_mongo.py`, the CWD is apps/api
load_dotenv(".env")

MONGO_URL = os.getenv("MONGODB_URL")
DB_NAME = os.getenv("MONGODB_DATABASE", "kureita_test")

async def test_mongo():
    print(f"Connecting to {MONGO_URL}...")
    client = AsyncIOMotorClient(MONGO_URL)
    
    try:
        # Ping
        await client.admin.command('ping')
        print("✓ Connected successfully!")
        
        db = client[DB_NAME]
        collection = db.test_collection
        
        # Insert
        doc = {"name": "Test Document", "status": "active"}
        result = await collection.insert_one(doc)
        print(f"✓ Inserted document with ID: {result.inserted_id}")
        
        # Find
        found = await collection.find_one({"_id": result.inserted_id})
        print(f"✓ Found document: {found}")
        
        # Delete
        await collection.delete_one({"_id": result.inserted_id})
        print("✓ Deleted document")
        
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_mongo())
