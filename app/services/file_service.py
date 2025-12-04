"""
Google Cloud Storage service for file uploads.
"""
import os
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
import mimetypes
from pathlib import Path

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from fastapi import UploadFile

from app.core.config import settings


logger = logging.getLogger(__name__)


class FileService:
    """Google Cloud Storage service for managing file uploads."""
    
    def __init__(self):
        try: 
            self.client = storage.Client(project=settings.GCS_PROJECT_ID)
            self.bucket = self.client.bucket(settings.GCS_BUCKET_NAME)
        except GoogleCloudError as e:
            logger.error(f"Failed to initialize Google Cloud Storage client: {e}")
            raise

    def _is_allowed_file(self, file: UploadFile) -> Tuple[bool, str]:
        """Check if the file has an allowed extension."""
        allowed_extensions = settings.ALLOWED_FILE_EXTENSIONS
        file_extension = Path(file.filename).suffix.lower() #type: ignore

        if file_extension not in allowed_extensions:
            return False, f"File type '{file_extension}' is not allowed."
        
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)
        if file_size > settings.MAX_UPLOAD_SIZE:
            return False, f"File size exceeds the maximum limit of {settings.MAX_UPLOAD_SIZE} bytes."
        
        if file_size == 0:
            return False, "File size is zero."
        return True, ""
    
    async def upload_file(self, file: UploadFile, user_id: int, metadata: Optional[dict] = None) -> dict:
        """Upload a file to Google Cloud Storage."""
        is_valid, message = self._is_allowed_file(file)
        if not is_valid:
            logger.warning(f"File validation failed: {message}")
            return {"success": False, "message": message}
        
        gcs_filename = f"user_{user_id}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        try:
            blob = self.bucket.blob(gcs_filename)
            content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream" #type: ignore
            blob_metatadata = {
                "original_filename": file.filename,
                "uploaded_by": str(user_id),
                "upload_time": datetime.now().isoformat()
            }
            if metadata:
                blob_metatadata.update(metadata)
            blob.metadata = blob_metatadata

            blob.upload_from_file(file.file, content_type=content_type, timeout=120)
            logger.info(f"File '{file.filename}' uploaded successfully as '{gcs_filename}'.")
            file_size = blob.size
            public_url = blob.public_url if blob.public_url else None

            return {
                "filename": file.filename,
                "gcs_path": gcs_filename,
                "file_size": file_size,
                "content_type": content_type,
                "public_url": public_url,
                "bucket": settings.GCS_BUCKET_NAME,
                "success": True,
            }
        except GoogleCloudError as e:
            logger.error(f"Failed to upload file '{file.filename}': {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while uploading file '{file.filename}': {e}")
            raise

    def delete_file(self, gcs_path: str) -> bool:
        """Delete a file from Google Cloud Storage."""
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            logger.info(f"File '{gcs_path}' deleted successfully.")
            return True
        except GoogleCloudError as e:
            logger.error(f"Failed to delete file '{gcs_path}': {e}")
            return False

    def generate_signed_url(self, gcs_path: str, expiration_minutes: int = 15) -> Optional[str]:
        """
        Generate a signed URL for accessing a file in Google Cloud Storage.
        """
        try:
            blob = self.bucket.blob(gcs_path)
            url = blob.generate_signed_url(
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            logger.info(f"Generated signed URL for '{gcs_path}' valid for {expiration_minutes} minutes.")
            return url
        except GoogleCloudError as e:
            logger.error(f"Failed to generate signed URL for '{gcs_path}': {e}")
            raise

    def get_file_content(self, gcs_path: str) -> bytes:
        """Retrieve the content of a file from Google Cloud Storage."""
        try:
            blob = self.bucket.blob(gcs_path)
            content = blob.download_as_bytes()
            logger.info(f"Retrieved content for file '{gcs_path}'.")
            return content
        except GoogleCloudError as e:
            logger.error(f"Failed to retrieve content for file '{gcs_path}': {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while retrieving content for file '{gcs_path}': {e}")
            raise

    def file_exists(self, gcs_path: str) -> bool:
        """Check if a file exists in Google Cloud Storage."""
        try:
            blob = self.bucket.blob(gcs_path)
            exists = blob.exists()
            logger.info(f"File existence check for '{gcs_path}': {exists}")
            return exists
        except GoogleCloudError as e:
            logger.error(f"Failed to check existence of file '{gcs_path}': {e}")
            return False
