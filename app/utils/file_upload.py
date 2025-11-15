"""
File upload utilities.
"""
import os
import uuid
from typing import Tuple

from fastapi import UploadFile

from app.core.config import settings


ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx"}


def is_allowed_file(filename: str) -> bool:
    """
    Check if file extension is allowed.

    Args:
        filename: Name of file

    Returns:
        True if file extension is allowed, False otherwise
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """
    Get file extension.

    Args:
        filename: Name of file

    Returns:
        File extension without dot
    """
    return filename.rsplit(".", 1)[1].lower() if "." in filename else ""


def generate_unique_filename(original_filename: str) -> str:
    """
    Generate a unique filename using UUID.

    Args:
        original_filename: Original filename

    Returns:
        Unique filename
    """
    ext = get_file_extension(original_filename)
    unique_name = f"{uuid.uuid4()}.{ext}"
    return unique_name


async def save_upload_file(upload_file: UploadFile) -> Tuple[str, str, int]:
    """
    Save uploaded file to disk.

    Args:
        upload_file: Uploaded file

    Returns:
        Tuple of (file_path, filename, file_size)

    Raises:
        ValueError: If file type is not allowed
    """
    if not is_allowed_file(upload_file.filename):
        raise ValueError(f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")

    # Create upload directory if it doesn't exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Generate unique filename
    unique_filename = generate_unique_filename(upload_file.filename)
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save file
    content = await upload_file.read()
    file_size = len(content)

    # Check file size
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise ValueError(
            f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE} bytes"
        )

    with open(file_path, "wb") as f:
        f.write(content)

    return file_path, unique_filename, file_size
