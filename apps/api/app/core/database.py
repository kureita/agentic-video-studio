from app.core.json_store import json_db

# Mocking the async connection functions to keep main.py happy (or we can remove them)
async def connect_to_mongo():
    print("✓ Using local JSON file storage (data/*.json)")

async def close_mongo_connection():
    pass

def get_database():
    return json_db

def get_projects_collection():
    return json_db.projects

def get_workflows_collection():
    return json_db.workflows

def get_generations_collection():
    return json_db.generations


