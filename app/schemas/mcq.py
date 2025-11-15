"""
Pydantic schemas for MCQ model.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class MCQBase(BaseModel):
    """Base MCQ schema."""

    question: str
    choices: List[str]
    correct_answer: str
    explanation: Optional[str] = None
    difficulty: str = "medium"
    topic: Optional[str] = None


class MCQCreate(MCQBase):
    """Schema for MCQ creation."""

    document_id: int


class MCQUpdate(BaseModel):
    """Schema for MCQ update."""

    question: Optional[str] = None
    choices: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None


class MCQInDB(MCQBase):
    """Schema for MCQ in database."""

    id: int
    document_id: int
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class MCQ(MCQInDB):
    """Schema for MCQ response."""

    pass


class MCQGenerate(BaseModel):
    """Schema for MCQ generation request."""

    document_id: int
    num_questions: int = 10
    difficulty: Optional[str] = None
    topic: Optional[str] = None


class MCQGenerateResponse(BaseModel):
    """Schema for MCQ generation response."""

    mcqs: List[MCQ]
    message: str
