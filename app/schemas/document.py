"""
Pydantic schemas for Document model.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentBase(BaseModel):
    """Base document schema."""

    title: str


class DocumentCreate(DocumentBase):
    """Schema for document creation."""

    pass


class DocumentUpdate(BaseModel):
    """Schema for document update."""

    title: Optional[str] = None


class DocumentInDB(DocumentBase):
    """Schema for document in database."""

    id: int
    filename: str
    file_path: str
    file_type: str
    file_size: int
    extracted_text: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class Document(DocumentInDB):
    """Schema for document response."""

    pass


class DocumentWithText(Document):
    """Schema for document response with full text."""

    pass
