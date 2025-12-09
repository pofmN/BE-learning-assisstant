import datetime
from typing import Optional
from pydantic import BaseModel

class CourseBase(BaseModel):
    """Base course schema."""
    title: Optional[str] = None
    description: Optional[str] = None

class CourseCreate(CourseBase):
    """Schema for course creation."""
    gcs_path: str
    language: Optional[str] = None # e.g., English, Vietnamese
    num_of_quizzes: Optional[int] = None
    level: Optional[str] = None # e.g., Beginner, Intermediate, Advanced, Mixed
    requirements: Optional[str] = None
    
class CourseInDB(CourseBase):
    """Schema for course in database."""
    id: int
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None

    class Config:
        """Pydantic config."""
        from_attributes = True
