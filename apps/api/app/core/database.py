from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.core.config import settings

# Global MongoDB client
db_client: AsyncIOMotorClient | None = None

def _create_mongo_client() -> AsyncIOMotorClient:
    """Create a MongoDB client with conservative timeouts for Lambda."""
    return AsyncIOMotorClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=10000,
        appname="kureita-api",
    )


async def connect_to_mongo():
    """Connect to MongoDB."""
    global db_client
    try:
        if settings.mongodb_url:
            db_client = _create_mongo_client()
            # Verify connection
            await db_client.admin.command('ping')
            db = db_client[settings.mongodb_database]
            await db.dodo_payment_ledger.create_index("payment_id", unique=True)
            # user_assets: compound index for fast user-scoped queries + dedup
            await db.user_assets.create_index([("user_id", 1), ("url", 1)])
            await db.user_assets.create_index([("user_id", 1), ("created_at", -1)])
            print("✓ Connected to MongoDB")
            return True
        else:
            print("⚠ MongoDB URL not found in settings")
            return False
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        # Do not crash app startup; handlers can return 503 if DB is unavailable.
        if db_client:
            db_client.close()
        db_client = None
        return False

async def close_mongo_connection():
    """Close MongoDB connection."""
    global db_client
    if db_client:
        db_client.close()
        print("✓ Closed MongoDB connection")

def get_database():
    """Get the database instance."""
    global db_client
    if db_client is None:
        # Lazy init fallback so requests can recover even if startup DB ping failed.
        if settings.mongodb_url:
            try:
                db_client = _create_mongo_client()
            except Exception:
                db_client = None
        else:
            db_client = None

    if db_client is None:
        raise ConnectionFailure("MongoDB client is not initialized")

    return db_client[settings.mongodb_database]


async def is_database_healthy() -> bool:
    """Best-effort DB health probe used by /health."""
    try:
        db = get_database()
        await db.command("ping")
        return True
    except Exception:
        return False

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
