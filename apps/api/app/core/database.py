from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# Global MongoDB client
db_client: AsyncIOMotorClient = None

async def connect_to_mongo():
    """Connect to MongoDB."""
    global db_client
    try:
        if settings.mongodb_url:
            db_client = AsyncIOMotorClient(settings.mongodb_url)
            # Verify connection
            await db_client.admin.command('ping')
            db = db_client[settings.mongodb_database]
            await db.dodo_payment_ledger.create_index("payment_id", unique=True)
            # user_assets: compound index for fast user-scoped queries + dedup
            await db.user_assets.create_index([("user_id", 1), ("url", 1)])
            await db.user_assets.create_index([("user_id", 1), ("created_at", -1)])
            print("✓ Connected to MongoDB")
        else:
            print("⚠ MongoDB URL not found in settings")
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        raise e

async def close_mongo_connection():
    """Close MongoDB connection."""
    global db_client
    if db_client:
        db_client.close()
        print("✓ Closed MongoDB connection")

def get_database():
    """Get the database instance."""
    if db_client is None:
        # Fallback for when connect_to_mongo hasn't been called (e.g. tests/scripts)
        # In a real app, this should probably raise an error or auto-connect
        return None
        
    return db_client[settings.mongodb_database]

def get_projects_collection():
    """Get the projects collection."""
    db = get_database()
    return db.projects

def get_workflows_collection():
    """Get the workflows collection."""
    db = get_database()
    return db.workflows

def get_generations_collection():
    """Get the generations collection."""
    db = get_database()
    return db.generations

def get_users_collection():
    """Get the users collection."""
    db = get_database()
    return db.users

def get_workflow_jobs_collection():
    """Get the workflow_jobs collection for Run All job orchestration."""
    db = get_database()
    return db.workflow_jobs