"""Folder schemas for request/response validation."""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class FolderBase(BaseModel):
    """Base folder schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Folder name")


class FolderCreate(FolderBase):
    """Schema for creating a new folder."""
    pass


class FolderUpdate(BaseModel):
    """Schema for updating a folder."""
    name: str = Field(..., min_length=1, max_length=255, description="New folder name")


class FolderInDB(FolderBase):
    """Folder schema with database fields."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class FolderWithCourseCount(FolderInDB):
    """Folder schema with course count."""
    course_count: int = 0
    
    class Config:
        from_attributes = True
