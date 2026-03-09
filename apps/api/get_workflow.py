import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson import json_util
import json
from dotenv import load_dotenv

load_dotenv('.env.local')

client = MongoClient(os.getenv('MONGODB_URL'))
db = client[os.getenv('MONGODB_DATABASE')]

doc = db.workflows.find_one({"_id": ObjectId("69abd41f469bc2bc7af63d3a")})
if not doc:
    doc = db.workflows.find_one({"_id": "69abd41f469bc2bc7af63d3a"})

print(json.dumps(doc, default=json_util.default, indent=2))
