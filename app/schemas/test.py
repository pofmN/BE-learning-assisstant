"""
Pydantic schemas for Test models.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TestAnswerSubmit(BaseModel):
    """Schema for submitting a test answer."""

    mcq_id: int
    user_answer: str


class TestSubmit(BaseModel):
    """Schema for submitting a complete test."""

    title: str
    answers: List[TestAnswerSubmit]


class TestAnswerResult(BaseModel):
    """Schema for test answer result."""

    mcq_id: int
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class TestResultBase(BaseModel):
    """Base test result schema."""

    title: str
    total_questions: int
    correct_answers: int
    score: float


class TestResultCreate(TestResultBase):
    """Schema for test result creation."""

    user_id: int


class TestResultInDB(TestResultBase):
    """Schema for test result in database."""

    id: int
    user_id: int
    completed_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class TestResult(TestResultInDB):
    """Schema for test result response."""

    pass


class TestResultDetailed(TestResult):
    """Schema for detailed test result with answers."""

    answers: List[TestAnswerResult]
