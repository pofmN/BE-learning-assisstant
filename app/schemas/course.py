from datetime import datetime
from typing import Literal, Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator


class CourseBase(BaseModel):
    """Base course schema."""
    title: Optional[str] = Field(None, description="Title of the course")
    description: Optional[str] = Field(None, description="Description of the course")
    language: Optional[str] = Field(None, description="Language of the course")
    level: Optional[str] = Field(None, description="Difficulty level of the course")
    requirements: Optional[str] = Field(None, description="Requirements for the course of users")
    question_type: Optional[List[str]] = Field(None, description="List of question types for the course")
    @field_validator('question_type', mode='before')
    @classmethod
    def parse_question_type(cls, v):
        """Ensure question_type is a list of strings."""
        if v is None:
            return None
        if isinstance(v, str):
            # Convert "multiple_choice,true_false" to ["multiple_choice", "true_false"]
            return [qt.strip() for qt in v.split(',') if qt.strip()]
        return v

class CourseInDB(CourseBase):
    """Schema for course in database."""
    id: int
    document_id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""
        from_attributes = True

class CourseCreate(BaseModel):
    """Schema for course creation."""
    document_id: int
    language: Optional[str] = "English"  # e.g., English, Vietnamese
    level: Optional[str] = "Mixed"  # e.g., Beginner, Intermediate, Advanced, Mixed
    requirements: Optional[str] = None
    question_type: Optional[List[str]] = ["multiple_choice"]  # e.g., multiple_choice, true_false

class CourseCreateResponse(BaseModel):
    """Response for course creation."""
    course_id: int
    status: str
    message: str

class CourseSectionBase(BaseModel):
    """Base schema for course section."""
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section detail content")
    section_order: int = Field(..., description="Order of the section in the course")
    cluster_id: int = Field(..., description="Reference to document chunk cluster")
    key_points: List[str] = Field(..., description="List of key points in the section")


class CourseSectionCreate(CourseSectionBase):
    """Schema for creating course section."""
    course_id: int

class CourseSectionList(CourseSectionCreate):
    """Schema for listing course sections."""
    sections: List[CourseSectionBase] = Field(..., description="List of course sections")


class CourseSectionInDB(CourseSectionBase):
    """Schema for course section in database."""
    id: int
    course_id: int
    created_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True

class MultipleChoiceData(BaseModel):
    """Data structure for 'multiple_choice' questions."""
    options: List[Dict[str, str]] = Field(description="List of choice objects, each having 'id' and 'text'.")
    correct_answer_id: str = Field(description="The 'id' of the correct choice.")
    shuffle: bool = True

class TrueFalseData(BaseModel):
    """Data structure for 'true_false' questions."""
    statement: str = Field(description="The full statement to be judged True or False.")
    correct_answer: bool = Field(description="The correct answer (true or false).")

class MatchingData(BaseModel):
    """Data structure for 'matching' questions (connections)."""
    left_side: List[Dict[str, str]] = Field(..., description="List of items on the left side (e.g., Terms).")
    right_side: List[Dict[str, str]] = Field(..., description="List of items on the right side (e.g., Definitions).")
    correct_matches: Dict[str, str] = Field(description="A dictionary mapping left_id to right_id (e.g., {'L1': 'R2'}).")
    shuffle_right_side: bool = True
    
    # Validator uses the correct Pydantic V2 decorator
    @field_validator('left_side', 'right_side', mode='before')
    @classmethod
    def check_min_length(cls, v):
        if len(v) < 2:
            raise ValueError('Matching sides must have at least 2 items')
        return v

# --- The Unified Quiz Schema ---

class QuizBase(BaseModel):
    """
    Flattened quiz schema compatible with OpenAI structured output.
    All fields are optional, validated based on question_type.
    """
    question: str = Field(..., description="The question text")
    question_type: Literal["multiple_choice", "true_false", "matching"] = Field(
        ..., 
        description="Type of question"
    )
    explanation: str = Field(..., description="Explanation of the correct answer")
    difficulty: Literal["easy", "medium", "hard"] = Field(
        default="medium",
        description="Difficulty level"
    )
    
    # Multiple Choice fields
    options: Optional[List[Dict[str, str]]] = Field(
        None, 
        description="List of choice objects with 'id' and 'text' keys"
    )
    correct_answer_id: Optional[str] = Field(
        None,
        description="The 'id' of the correct choice for multiple choice"
    )
    shuffle: Optional[bool] = Field(
        None,
        description="Whether to shuffle options for multiple choice"
    )
    
    # True/False fields
    statement: Optional[str] = Field(
        None,
        description="The statement for true/false questions"
    )
    correct_answer: Optional[bool] = Field(
        None,
        description="The correct boolean answer for true/false"
    )
    
    # Matching fields
    left_side: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Left side items for matching questions"
    )
    right_side: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Right side items for matching questions"
    )
    correct_matches: Optional[Dict[str, str]] = Field(
        None,
        description="Mapping of left_id to right_id for matching"
    )
    shuffle_right_side: Optional[bool] = Field(
        None,
        description="Whether to shuffle right side for matching"
    )
    
    @field_validator('options', 'left_side', 'right_side', mode='before')
    @classmethod
    def validate_lists(cls, v):
        """Ensure lists have minimum items when provided."""
        if v is not None and len(v) > 0 and len(v) < 2:
            raise ValueError('Lists must have at least 2 items')
        return v
    
    def to_db_format(self) -> Dict[str, Any]:
        """Convert to database storage format."""
        if self.question_type == "multiple_choice":
            return {
                "options": self.options,
                "correct_answer_id": self.correct_answer_id,
                "shuffle": self.shuffle if self.shuffle is not None else True
            }
        elif self.question_type == "true_false":
            return {
                "statement": self.statement,
                "correct_answer": self.correct_answer
            }
        elif self.question_type == "matching":
            return {
                "left_side": self.left_side,
                "right_side": self.right_side,
                "correct_matches": self.correct_matches,
                "shuffle_right_side": self.shuffle_right_side if self.shuffle_right_side is not None else True
            }
        return {}
    
class QuizList(BaseModel):
    """List of quiz questions."""
    questions: List[QuizBase] = Field(..., description="Array of quiz questions")

class QuizCreate(BaseModel):
    """Schema for creating quiz."""
    course_id: int
    section_id: Optional[int] = None
    question: str
    question_type: str
    question_data: Dict[str, Any]
    explanation: str
    difficulty: str = "medium"


class QuizInDB(BaseModel):
    """Schema for quiz in database."""
    id: int
    course_id: int
    section_id: Optional[int] = None
    question: str
    question_type: str
    question_data: Dict[str, Any]
    explanation: str
    difficulty: str
    created_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True

class StudiesNoteBase(BaseModel):
    """Schema for studies note."""
    title: str = Field(..., description="Title of the study note")
    content: str = Field(..., description="Detailed content of the study note")

class StudiesNoteList(BaseModel):
    """List of studies notes."""
    notes: List[StudiesNoteBase] = Field(..., description="Array of study notes")

class StudiesNoteInDB(StudiesNoteBase):
    """Schema for studies note in database."""
    id: int
    course_id: int
    section_id: Optional[int] = None
    created_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True

class CourseResponse(CourseInDB):
    """Schema for course response with sections and quizzes."""
    sections: List[CourseSectionInDB] = []
    quizzes: List[QuizInDB] = []

    class Config:
        """Pydantic config."""
        from_attributes = True

# ============= COURSE SHARING =============

class CourseShareCreate(BaseModel):
    """
    Schema for creating a share link.
    
    Fields:
    - is_public: Allow anonymous viewing (default: True)
    - expires_in_days: Optional expiration (0 or None = never expires)
    """
    is_public: bool = Field(
        default=True,
        description="If True, anyone with link can view. If False, login required."
    )
    expires_in_days: Optional[int] = Field(
        default=None,
        description="Number of days until link expires. 0 or None means never expires.",
        ge=0,  # Allow 0 for "never expires"
        le=365  # Max 1 year
    )

class CourseShareResponse(BaseModel):
    """
    Response after creating a share link.
    
    Returns the full URL and metadata for the frontend to display.
    """
    id: int
    course_id: int
    share_token: str
    share_url: str  # Full URL with domain
    is_public: bool
    expires_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class CourseShareList(BaseModel):
    """Schema for listing share links (for course owner)."""
    id: int
    share_token: str
    share_url: str
    is_public: bool
    expires_at: Optional[datetime]
    created_at: datetime
    access_count: int = 0  # Future: track how many people used this link
    
    class Config:
        from_attributes = True


class CourseEnrollmentResponse(BaseModel):
    """Response when a user enrolls via share link."""
    enrolled: bool
    course_id: int
    course_title: str
    message: str
    access_level: str  # "view_only" or "full"


class CourseWithAccess(CourseInDB):
    """
    Extended course schema that includes access information.
    Used when listing courses to show ownership vs enrollment.
    """
    is_owner: bool  # True if user uploaded the document
    enrolled_via: Optional[str] = None  # How user got access (if enrolled)
    enrolled_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

