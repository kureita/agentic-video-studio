import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from uuid import uuid4
from bson import ObjectId

class JsonCursor:
    """Mock MongoDB Cursor for JSON store."""
    def __init__(self, items: List[Dict]):
        self.items = items
        self._skip = 0
        self._limit = 0
        self._sort_key = None
        self._sort_order = 1

    def sort(self, key_or_list, direction=1):
        if isinstance(key_or_list, str):
            self._sort_key = key_or_list
            self._sort_order = direction
        return self

    def skip(self, skip: int):
        self._skip = skip
        return self

    def limit(self, limit: int):
        self._limit = limit
        return self

    async def to_list(self, length: int = None):
        # Sort
        if self._sort_key:
            self.items.sort(
                key=lambda x: x.get(self._sort_key, ""),
                reverse=(self._sort_order == -1)
            )
        
        # Apply skip
        start = self._skip
        
        # Apply limit
        end = start + (self._limit if self._limit > 0 else len(self.items))
        if length:
            end = min(end, start + length)
            
        return self.items[start:end]

class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id

class DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count

class UpdateResult:
    def __init__(self, matched_count, modified_count):
        self.matched_count = matched_count
        self.modified_count = modified_count

class JsonCollection:
    """Mock MongoDB Collection backing to a JSON file."""
    def __init__(self, name: str, data_dir: Path):
        self.name = name
        self.file_path = data_dir / f"{name}.json"
        self._ensure_file()

    def _ensure_file(self):
        if not self.file_path.exists():
            self._save_data([])

    def _load_data(self) -> List[Dict]:
        try:
            with open(self.file_path, "r") as f:
                content = f.read()
                if not content:
                    return []
                data = json.loads(content, object_hook=self._datetime_decoder)
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_data(self, data: List[Dict]):
        with open(self.file_path, "w") as f:
            json.dump(data, f, default=self._json_serializer, indent=2)

    def _json_serializer(self, obj):
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return str(obj)

    def _datetime_decoder(self, dct):
        for k, v in dct.items():
            if isinstance(v, str) and "T" in v and len(v) > 19:
                try:
                    # Simple attempt to revive datetimes
                    dct[k] = datetime.fromisoformat(v)
                except ValueError:
                    pass
            # Revive specific fields we know are IDs
            if k == "_id" and isinstance(v, str):
                try:
                    dct[k] = ObjectId(v)
                except:
                    pass
        return dct

    def _matches_query(self, doc: Dict, query: Dict) -> bool:
        for k, v in query.items():
            if doc.get(k) != v:
                return False
        return True

    def find(self, query: Dict) -> JsonCursor:
        data = self._load_data()
        filtered = [d for d in data if self._matches_query(d, query)]
        return JsonCursor(filtered)

    async def find_one(self, query: Dict) -> Optional[Dict]:
        data = self._load_data()
        for doc in data:
            if self._matches_query(doc, query):
                return doc
        return None

    async def insert_one(self, document: Dict) -> InsertOneResult:
        data = self._load_data()
        if "_id" not in document:
            document["_id"] = ObjectId()
        
        data.append(document)
        self._save_data(data)
        return InsertOneResult(document["_id"])

    async def update_one(self, query: Dict, update: Dict) -> UpdateResult:
        data = self._load_data()
        matched = 0
        modified = 0
        
        for doc in data:
            if self._matches_query(doc, query):
                matched += 1
                if "$set" in update:
                    doc.update(update["$set"])
                    modified += 1
                # Handle direct updates if needed, though $set is standard mongo
                self._save_data(data)
                break
                
        return UpdateResult(matched, modified)

    async def find_one_and_update(self, query: Dict, update: Dict, return_document=False) -> Optional[Dict]:
        await self.update_one(query, update)
        if return_document:
            return await self.find_one(query)
        # return original would require fetching before update, keeping simple for now
        return await self.find_one(query)

    async def delete_one(self, query: Dict) -> DeleteResult:
        data = self._load_data()
        initial_len = len(data)
        
        new_data = [doc for doc in data if not self._matches_query(doc, query)]
        
        if len(new_data) < initial_len:
            self._save_data(new_data)
            return DeleteResult(1)
        return DeleteResult(0)
    
    # Mock index creation (noop)
    async def create_index(self, *args, **kwargs):
        pass

class JsonDb:
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.collections: Dict[str, JsonCollection] = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = JsonCollection(name, self.data_dir)
        return self.collections[name]
    
    def __getattr__(self, name):
        return self[name]

# Global instance
json_db = JsonDb()
