"""
Pydantic schemas for review quiz system.
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class CourseCompletionStatus(BaseModel):
    """Course completion status for eligibility check."""
    total_sections: int
    completed_sections: int
    total_quizzes: int
    attempted_quizzes: int
    completion_percentage: float


class EligibilityResponse(BaseModel):
    """Response for eligibility check."""
    eligible: bool
    course_completion: CourseCompletionStatus
    existing_review: Optional[Dict] = None  # {session_id, status} if resumable
    message: str


class QuestionDistribution(BaseModel):
    """Distribution of questions by difficulty/performance."""
    weak_topics: int
    medium_topics: int
    strong_topics: int


class ReviewQuizGenerateResponse(BaseModel):
    """Response after generating review quiz."""
    session_id: int
    total_questions: int
    selection_strategy: str
    question_distribution: QuestionDistribution
    message: str


class TopicPerformance(BaseModel):
    """Performance comparison for a specific topic/section."""
    section: str
    section_id: Optional[int]
    original_score: float
    review_score: float
    improvement: float
    status: str  # "improving", "regression", "stable"


class Recommendation(BaseModel):
    """Study recommendation."""
    priority: str  # "high", "medium", "low"
    topic: str
    suggestion: str
    reason: str
    study_resources: List[str] = Field(default_factory=list)


class PerformanceBreakdown(BaseModel):
    """Question-level performance breakdown."""
    improved: int
    regressed: int
    persistent_weak: int
    consistent_strong: int


class PerformanceSummary(BaseModel):
    """Overall performance summary."""
    original_avg_score: float
    review_score: float
    improvement: float
    grade: str  # A, B, C, D, F


class NextSteps(BaseModel):
    """Suggested next steps for study."""
    weak_topics: List[str]
    suggested_study_time: str
    review_again_after: str
    confidence_level: str  # "low", "medium", "high"


class ReviewInsightsResponse(BaseModel):
    """Complete insights response after review completion."""
    analysis_id: int
    review_session_id: int
    completion_date: datetime
    
    performance_summary: PerformanceSummary
    question_breakdown: PerformanceBreakdown
    topic_analysis: List[TopicPerformance]
    recommendations: List[Recommendation]
    next_steps: NextSteps


class PerformanceReport(BaseModel):
    """Internal performance analysis report."""
    improved_questions: List[int]
    regressed_questions: List[int]
    persistent_weaknesses: List[int]
    consistent_strengths: List[int]
    improvement_rate: float
    topic_analysis: Dict[str, Dict]  # topic -> {original, review, improvement}
    weak_topics: List[str]
    strong_topics: List[str]
