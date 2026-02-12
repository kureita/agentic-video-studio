from functools import lru_cache
from app.core.config import settings
from app.services.storage_service import StorageService, LocalStorageService, S3StorageService

@lru_cache
def get_storage_service() -> StorageService:
    """Return the storage service implementation based on settings."""
    if settings.storage_type == "s3":
        return S3StorageService()
    return LocalStorageService()
