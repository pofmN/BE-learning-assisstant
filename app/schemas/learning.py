"""
Pydantic schemas for Learning Progress model.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class LearningProgressBase(BaseModel):
    """Base learning progress schema."""

    topic: str
    total_attempts: int = 0
    correct_attempts: int = 0
    accuracy: float = 0.0
    weak_areas: Optional[List[str]] = None


class LearningProgressCreate(LearningProgressBase):
    """Schema for learning progress creation."""

    user_id: int


class LearningProgressUpdate(BaseModel):
    """Schema for learning progress update."""

    total_attempts: Optional[int] = None
    correct_attempts: Optional[int] = None
    accuracy: Optional[float] = None
    weak_areas: Optional[List[str]] = None


class LearningProgressInDB(LearningProgressBase):
    """Schema for learning progress in database."""

    id: int
    user_id: int
    last_studied: datetime
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class LearningProgress(LearningProgressInDB):
    """Schema for learning progress response."""

    pass


class TopicRecommendation(BaseModel):
    """Schema for topic recommendation."""

    topic: str
    reason: str
    priority: str  # high, medium, low


class WeakArea(BaseModel):
    """Schema for weak area analysis."""

    topic: str
    accuracy: float
    total_attempts: int
    suggestions: List[str]
