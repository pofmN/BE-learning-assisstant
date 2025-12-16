"""
API endpoints for learning progress and statistics.
"""
from typing import List, Optional, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.user import User
from app.models.course import Course, CourseSection, Quiz, FlashCard
from app.models.quiz_attempt import QuizSession, QuizAttempt, FlashcardReview
from pydantic import BaseModel, ConfigDict

router = APIRouter()


# ============= Schemas =============

class CourseProgress(BaseModel):
    """Schema for course progress."""
    model_config = ConfigDict(from_attributes=True)
    
    course_id: int
    course_title: str
    total_sections: int
    quiz_sessions_completed: int
    avg_quiz_score: float
    flashcards_total: int
    flashcards_reviewed: int
    last_activity: Optional[datetime]
    completion_percentage: float


class SectionProgress(BaseModel):
    """Schema for section progress."""
    model_config = ConfigDict(from_attributes=True)
    
    section_id: int
    section_title: str
    quizzes_total: int
    quizzes_attempted: int
    quiz_avg_score: float
    flashcards_total: int
    flashcards_reviewed: int
    is_completed: bool


class OverallStats(BaseModel):
    """Schema for overall learning statistics."""
    model_config = ConfigDict(from_attributes=True)
    
    total_courses: int
    courses_in_progress: int
    total_quiz_sessions: int
    total_quizzes_attempted: int
    avg_quiz_score: float
    total_flashcards_reviewed: int
    total_study_time_minutes: int
    current_streak_days: int


# ============= Progress Endpoints =============

@router.get("/courses/{course_id}/progress", response_model=CourseProgress)
def get_course_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get detailed progress for a specific course.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get sections count
    sections = db.query(CourseSection).filter(CourseSection.course_id == course_id).all()
    total_sections = len(sections)
    
    # Get quiz sessions
    quiz_sessions = db.query(QuizSession).filter(
        QuizSession.course_id == course_id,
        QuizSession.user_id == current_user.id,  
        QuizSession.status == "completed"
    ).all()
    
    quiz_sessions_completed = len(quiz_sessions)
    avg_quiz_score = sum(s.score_percentage for s in quiz_sessions) / quiz_sessions_completed if quiz_sessions_completed > 0 else 0
    
    # Get flashcard stats
    flashcards = db.query(FlashCard).filter(FlashCard.course_id == course_id).all()
    flashcards_total = len(flashcards)
    
    flashcard_ids = [f.id for f in flashcards]
    reviewed_count = db.query(distinct(FlashcardReview.flashcard_id)).filter(
        FlashcardReview.flashcard_id.in_(flashcard_ids),
        FlashcardReview.user_id == current_user.id  
    ).count()
    
    # Last activity
    last_activity = None
    if quiz_sessions:
        last_quiz = max(quiz_sessions, key=lambda s: s.completed_at or s.started_at)
        last_activity = last_quiz.completed_at or last_quiz.started_at
    
    # Calculate completion percentage
    completion = 0
    if quiz_sessions_completed > 0:
        completion += 50  # 50% for attempting quizzes
    if flashcards_total > 0 and reviewed_count / flashcards_total > 0.5:
        completion += 50  # 50% for reviewing flashcards
    
    return CourseProgress(
        course_id=course_id,
        course_title=str(course.title),  # type: ignore
        total_sections=total_sections,
        quiz_sessions_completed=quiz_sessions_completed,
        avg_quiz_score=float(avg_quiz_score),  # type: ignore
        flashcards_total=flashcards_total,
        flashcards_reviewed=int(reviewed_count),
        last_activity=last_activity,  # type: ignore
        completion_percentage=float(completion)
    )


@router.get("/courses/{course_id}/sections/{section_id}/progress", response_model=List[SectionProgress])
def get_sections_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get progress for all sections in a course.
    """
    sections = db.query(CourseSection).filter(CourseSection.course_id == course_id).all()
    
    result = []
    for section in sections:
        # Get quizzes for section
        quizzes = db.query(Quiz).filter(Quiz.section_id == section.id).all()
        quizzes_total = len(quizzes)
        
        # Get quiz attempts for this section
        quiz_ids = [q.id for q in quizzes]
        attempts = db.query(QuizAttempt).filter(
            QuizAttempt.quiz_id.in_(quiz_ids),
            QuizAttempt.user_id == current_user.id  
        ).all()
        
        quizzes_attempted = len(set(a.quiz_id for a in attempts))
        quiz_avg_score = (sum(1 for a in attempts if bool(a.is_correct)) / len(attempts) * 100) if attempts else 0  
        
        # Get flashcards for section
        flashcards = db.query(FlashCard).filter(FlashCard.section_id == section.id).all()
        flashcards_total = len(flashcards)
        
        flashcard_ids = [f.id for f in flashcards]
        reviewed_count = db.query(distinct(FlashcardReview.flashcard_id)).filter(
            FlashcardReview.flashcard_id.in_(flashcard_ids),
            FlashcardReview.user_id == current_user.id  
        ).count()
        
        # Determine if section is completed
        is_completed = (
            quizzes_total > 0 and quizzes_attempted >= quizzes_total and
            flashcards_total > 0 and reviewed_count >= flashcards_total
        )
        
        result.append(SectionProgress(
            section_id=int(section.id),  # type: ignore
            section_title=str(section.title),  # type: ignore
            quizzes_total=quizzes_total,
            quizzes_attempted=quizzes_attempted,
            quiz_avg_score=float(quiz_avg_score),
            flashcards_total=flashcards_total,
            flashcards_reviewed=int(reviewed_count),
            is_completed=bool(is_completed)
        ))
    
    return result


@router.get("/stats/overview", response_model=OverallStats)
def get_overall_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get overall learning statistics for the user.
    """
    # Get all user's courses (through documents they own)
    from app.models.document import Document
    documents = db.query(Document).filter(Document.owner_id == current_user.id).all()
    doc_ids = [d.id for d in documents]
    
    courses = db.query(Course).filter(Course.document_id.in_(doc_ids)).all()
    total_courses = len(courses)
    courses_in_progress = sum(1 for c in courses if c.status == "processing" or c.status == "completed") #type: ignore
    
    # Quiz stats
    course_ids = [c.id for c in courses]
    quiz_sessions = db.query(QuizSession).filter(
        QuizSession.course_id.in_(course_ids),
        QuizSession.user_id == current_user.id  
    ).all()
    
    total_quiz_sessions = len(quiz_sessions)
    completed_sessions = [s for s in quiz_sessions if s.status == "completed"] #type: ignore
    avg_quiz_score = sum(s.score_percentage for s in completed_sessions) / len(completed_sessions) if completed_sessions else 0
    
    # Count total quiz attempts
    total_quizzes_attempted = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == current_user.id  
    ).count()
    
    # Flashcard stats
    total_flashcards_reviewed = db.query(FlashcardReview).filter(
        FlashcardReview.user_id == current_user.id  
    ).count()
    
    # Calculate study time (from quiz sessions)
    total_study_time = 0
    for session in quiz_sessions:
        if session.completed_at and session.started_at: #type: ignore
            duration = (session.completed_at - session.started_at).total_seconds()
            total_study_time += duration
    
    total_study_time_minutes = int(total_study_time / 60)
    
    # Calculate study streak
    current_streak = _calculate_study_streak(db, int(current_user.id))  # type: ignore  
    
    return OverallStats(
        total_courses=int(total_courses),
        courses_in_progress=int(courses_in_progress),
        total_quiz_sessions=int(total_quiz_sessions),
        total_quizzes_attempted=int(total_quizzes_attempted),
        avg_quiz_score=float(avg_quiz_score),  # type: ignore
        total_flashcards_reviewed=int(total_flashcards_reviewed),
        total_study_time_minutes=int(total_study_time_minutes),
        current_streak_days=int(current_streak)
    )


# ============= Helper Functions =============

def _calculate_study_streak(db: Session, user_id: int) -> int:
    """
    Calculate current study streak (consecutive days with activity).
    """
    # Get all quiz sessions ordered by date
    sessions = db.query(QuizSession).filter(
        QuizSession.user_id == user_id
    ).order_by(QuizSession.started_at.desc()).all()
    
    if not sessions:
        return 0
    
    # Group by date
    activity_dates = set()
    for session in sessions:
        activity_dates.add(session.started_at.date())
    
    # Calculate streak
    streak = 0
    current_date = datetime.now().date()
    
    while current_date in activity_dates:
        streak += 1
        current_date -= timedelta(days=1)
    
    return streak
