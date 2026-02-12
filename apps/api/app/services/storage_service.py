from abc import ABC, abstractmethod
import os
import shutil
import boto3
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from fastapi import UploadFile
from botocore.exceptions import NoCredentialsError

from app.core.config import settings

class StorageService(ABC):
    """Abstract base class for storage services."""
    
    @abstractmethod
    async def upload_file(self, file_data: bytes | UploadFile, filename: str, content_type: str = None) -> str:
        """Upload a file and return its URL."""
        pass

    @abstractmethod
    async def delete_file(self, file_url: str) -> bool:
        """Delete a file by its URL."""
        pass


class LocalStorageService(StorageService):
    """Stores files in the local static directory."""
    
    def __init__(self):
        self.upload_dir = Path("static/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        # Ensure other static dirs exist too, just in case
        Path("static/videos").mkdir(parents=True, exist_ok=True)
        Path("static/images").mkdir(parents=True, exist_ok=True)
        Path("static/audio").mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file_data: bytes | UploadFile, filename: str, content_type: str = None) -> str:
        # Generate unique filename if not provided or to avoid collisions? 
        # For now assume filename is sufficiently unique or caller handles it.
        # But let's be safe and prepend uuid if it looks generic
        
        # Actually, let's keep the existing logic from assets.py roughly:
        # But here we want a general service.
        
        # Sanitizing filename
        safe_filename = Path(filename).name
        
        # Determine path based on extension/type? 
        # For MVP, put everything in uploads or specific folders?
        # Let's organize by type if possible, or just dump in uploads for simplicity
        # implementation match: assets.py used static/uploads.
        
        file_path = self.upload_dir / safe_filename
        
        # Handle UploadFile vs bytes
        if isinstance(file_data, UploadFile):
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file_data.file, buffer)
        else:
            with open(file_path, "wb") as buffer:
                buffer.write(file_data)
                
        # Construct URL
        base_url = settings.api_base_url or ""
        if base_url.endswith("/"):
            base_url = base_url[:-1]
            
        return f"{base_url}/static/uploads/{safe_filename}"

    async def delete_file(self, file_url: str) -> bool:
        # Extract filename from URL
        # URL: http://localhost:8000/static/uploads/filename.ext
        try:
            filename = file_url.split("/")[-1]
            file_path = self.upload_dir / filename
            if file_path.exists():
                os.remove(file_path)
                return True
        except Exception as e:
            print(f"Error deleting file {file_url}: {e}")
        return False


class S3StorageService(StorageService):
    """Stores files in AWS S3."""
    
    def __init__(self):
        self.bucket = settings.s3_bucket
        self.region = settings.aws_region
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=self.region,
            endpoint_url=settings.s3_endpoint if settings.s3_endpoint else None
        )

    async def upload_file(self, file_data: bytes | UploadFile, filename: str, content_type: str = None) -> str:
        try:
            # S3 Key (path in bucket)
            # Organizing by date to avoid huge flat lists
            date_prefix = datetime.now().strftime("%Y/%m/%d")
            key = f"uploads/{date_prefix}/{filename}"
            
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
                # Inline disposition for viewing in browser
                extra_args['ContentDisposition'] = 'inline'

            if isinstance(file_data, UploadFile):
                # Reset file pointer just in case
                await file_data.seek(0)
                self.s3_client.upload_fileobj(
                    file_data.file, 
                    self.bucket, 
                    key, 
                    ExtraArgs=extra_args
                )
            else:
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=file_data,
                    **extra_args
                )

            # Return URL
            # If standard S3
            if not settings.s3_endpoint:
                url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
            else:
                 # Custom endpoint (e.g. MinIO, R2)
                 url = f"{settings.s3_endpoint}/{self.bucket}/{key}"
            
            return url

        except NoCredentialsError:
            print("Credentials not available")
            raise Exception("AWS Credentials not available")
        except Exception as e:
            print(f"S3 Upload Error: {e}")
            raise e

    async def delete_file(self, file_url: str) -> bool:
        try:
            # Parse key from URL
            # basic strategy: remove domain part
            # This is tricky if URL format varies. 
            # For now assume standard S3 URL format or save Key separately?
            # MVP: Try to extract key by splitting known parts
            
            # Example: https://bucket.s3.region.amazonaws.com/uploads/2023/01/01/file.jpg
            # Key: uploads/2023/01/01/file.jpg
            
            from urllib.parse import urlparse
            path = urlparse(file_url).path
            if path.startswith("/"):
                path = path[1:]
                
            self.s3_client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except Exception as e:
            print(f"S3 Delete Error: {e}")
            return False
