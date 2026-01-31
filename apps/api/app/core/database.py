from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional

from app.core.config import settings


class Database:
    """MongoDB database connection manager."""

    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


db = Database()


async def connect_to_mongo():
    """Connect to MongoDB."""
    try:
        db.client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
        )
        db.db = db.client[settings.mongodb_database]
        
        # Test connection
        await db.client.admin.command("ping")
        
        # Create indexes
        await create_indexes()
        
        print(f"✓ Connected to MongoDB: {settings.mongodb_database}")
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
        print("  Hint: If using Atlas, URL-encode special chars in password (@ → %40, etc.)")
        raise


async def close_mongo_connection():
    """Close MongoDB connection."""
    if db.client:
        db.client.close()
        print("Closed MongoDB connection")


async def create_indexes():
    """Create database indexes for better query performance."""
    if db.db is None:
        return
    
    # Projects collection indexes
    projects = db.db.projects
    await projects.create_index("created_at")
    await projects.create_index("status")
    await projects.create_index("website_url")


def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance."""
    if db.db is None:
        raise RuntimeError("Database not connected")
    return db.db


# Collection helpers
def get_projects_collection():
    """Get the projects collection."""
    return get_database().projects


def get_generations_collection():
    """Get the generations collection (for tracking generation jobs)."""
    return get_database().generations

