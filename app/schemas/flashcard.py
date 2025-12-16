from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class FlashCardBase(BaseModel):
    """Schema for flashcard."""
    question: str = Field(..., description="Front of the flashcard")
    answer: str = Field(..., description="Back of the flashcard")

class FlashCardList(BaseModel):
    """List of flashcards."""
    flashcards: List[FlashCardBase] = Field(..., description="Array of flashcards")

class FlashCardInDB(FlashCardBase):
    """Schema for flashcard in database."""
    id: int
    course_id: int
    section_id: Optional[int] = None
    created_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True

class FlashcardResponse(BaseModel):
    """Schema for flashcard response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    course_id: int
    section_id: Optional[int]
    question: str
    answer: str
    times_reviewed: int
    avg_confidence: float
    next_review: Optional[datetime]


class FlashcardReviewSubmit(BaseModel):
    """Schema for submitting flashcard review."""
    flashcard_id: int
    confidence_level: int = Field(..., ge=1, le=5, description="Confidence level 1-5")
    time_spent: Optional[int] = None


class FlashcardStudyStatsResponse(BaseModel):
    """Schema for flashcard study session summary."""
    model_config = ConfigDict(from_attributes=True)
    
    cards_reviewed: int
    avg_confidence: float
    total_time_seconds: int
    cards_to_review: int

class FlashcardStudyInSectionResponse(FlashcardStudyStatsResponse):
    """Schema for flashcard study session summary by section."""
    model_config = ConfigDict(from_attributes=True)
    
    section_id: int

class FlashcardStudyInCourseResponse(FlashcardStudyStatsResponse):
    """Schema for flashcard study session summary by course."""
    model_config = ConfigDict(from_attributes=True)
    
    course_id: int