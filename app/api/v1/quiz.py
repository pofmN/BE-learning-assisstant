"""
API endpoints for quiz interactions - taking quizzes, reviewing results, etc.
"""
from typing import List, Optional, Any, Dict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.user import User
from app.models.course import Course, CourseSection, Quiz
from app.models.quiz_attempt import QuizSession, QuizAttempt
from pydantic import BaseModel, Field, field_validator

router = APIRouter()


# ============= Request/Response Schemas =============

class QuizSessionCreate(BaseModel):
    """Schema for starting a quiz session."""
    course_id: int
    section_id: Optional[int] = None
    
    @field_validator('section_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty string or null-like values to None."""
        if v in ('', 'null', 'undefined', None):
            return None
        return v


class QuizSessionResponse(BaseModel):
    """Schema for quiz session response."""
    session_id: int
    course_id: int
    section_id: Optional[int]
    total_questions: int
    status: str
    started_at: datetime
    
    class Config:
        from_attributes = True


class QuizAnswerSubmit(BaseModel):
    """
    Schema for submitting a quiz answer.
    
    The user_answer structure varies by question_type:
    
    **Multiple Choice:**
    ```json
    {
        "quiz_id": 1,
        "user_answer": {
            "selected_id": "option_a"
        },
        "time_spent": 30
    }
    ```
    
    **True/False:**
    ```json
    {
        "quiz_id": 2,
        "user_answer": {
            "answer": true
        },
        "time_spent": 15
    }
    ```
    
    **Matching:**
    ```json
    {
        "quiz_id": 3,
        "user_answer": {
            "matches": {
                "term_1": "definition_a",
                "term_2": "definition_b"
            }
        },
        "time_spent": 60
    }
    ```
    
    **Short Answer:**
    ```json
    {
        "quiz_id": 4,
        "user_answer": {
            "answer": "photosynthesis"
        },
        "time_spent": 45
    }
    ```
    """
    quiz_id: int = Field(..., description="ID of the quiz question being answered")
    user_answer: Dict[str, Any] = Field(
        ..., 
        description="User's answer (structure depends on question_type)",
        examples=[
            {"selected_id": "option_a"},  # Multiple choice
            {"answer": True},  # True/False
            {"matches": {"term_1": "def_a", "term_2": "def_b"}},  # Matching
            {"answer": "photosynthesis"}  # Short answer
        ]
    )
    time_spent: Optional[int] = Field(
        default=None, 
        description="Time spent on this question in seconds",
        ge=0
    )


class QuizAttemptResponse(BaseModel):
    """
    Schema for quiz attempt response.
    
    Returns the graded attempt with feedback.
    The `correct_answer` structure matches the question_type format.
    """
    attempt_id: int = Field(..., description="Unique ID of this attempt")
    quiz_id: int = Field(..., description="ID of the quiz question")
    is_correct: bool = Field(..., description="Whether the answer was correct")
    user_answer: Dict[str, Any] = Field(..., description="The user's submitted answer")
    correct_answer: Dict[str, Any] = Field(
        ..., 
        description="The correct answer with full question_data structure"
    )
    explanation: Optional[str] = Field(None, description="Explanation of the correct answer")
    question: str = Field(..., description="The question text")
    question_type: str = Field(
        ..., 
        description="Type of question: multiple_choice, true_false, matching, or short_answer"
    )


class QuizSessionResult(BaseModel):
    """Schema for completed quiz session results."""
    session_id: int
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    score_percentage: float
    completed_at: datetime
    attempts: List[QuizAttemptResponse]


# ============= Quiz List Endpoints =============
@router.get("/courses/{course_id}/quizzes", response_model=List[Dict[str, Any]])
def get_course_quizzes(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get all quizzes for a course.
    Returns quizzes with correct answers.
    """
    # Verify course exists and user has access
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get quizzes
    query = db.query(Quiz).filter(Quiz.course_id == course_id)
    
    quizzes = query.all()
    
    # Return questions with correct answers
    return [
        {
            "quiz_id": q.id,
            "question": q.question,
            "question_type": q.question_type,
            "question_data": q.question_data,  # Contains options but not correct answer
            "difficulty": q.difficulty
        }
        for q in quizzes
    ]


# ============= Quiz Session Endpoints =============

@router.post("/sessions/start", response_model=QuizSessionResponse, status_code=status.HTTP_201_CREATED)
def start_quiz_session(
    session_data: QuizSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Start a new quiz session for a course or specific section.
    Returns session_id and list of quiz questions.
    """
    # Verify course exists and user has access
    course = db.query(Course).filter(Course.id == session_data.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get quizzes for session
    query = db.query(Quiz).filter(Quiz.course_id == session_data.course_id)
    if session_data.section_id:
        query = query.filter(Quiz.section_id == session_data.section_id)
    
    quizzes = query.all()
    if not quizzes:
        raise HTTPException(status_code=404, detail="No quizzes found for this course/section")
    
    # Create quiz session
    quiz_session = QuizSession(
        user_id=current_user.id,  # type: ignore
        course_id=session_data.course_id,
        section_id=session_data.section_id,
        total_questions=len(quizzes),
        status="in_progress"
    )
    db.add(quiz_session)
    db.commit()
    db.refresh(quiz_session)
    
    return QuizSessionResponse(
        session_id=quiz_session.id,  # type: ignore
        course_id=quiz_session.course_id, # type: ignore
        section_id=quiz_session.section_id, # type: ignore
        total_questions=quiz_session.total_questions, # type: ignore
        status=quiz_session.status, # type: ignore
        started_at=quiz_session.started_at # type: ignore
    )


@router.get("/sessions/{session_id}/questions", response_model=List[Dict[str, Any]])
def get_session_questions(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get all questions for a quiz session.
    Returns questions WITHOUT correct answers (for taking the quiz).
    """
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id,
        QuizSession.user_id == current_user.id  # type: ignore
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    # Get quizzes
    query = db.query(Quiz).filter(Quiz.course_id == session.course_id)
    if session.section_id:  # type: ignore
        query = query.filter(Quiz.section_id == session.section_id)
    
    quizzes = query.all()
    
    # Return questions without correct answers
    return [
        {
            "quiz_id": q.id,
            "question": q.question,
            "question_type": q.question_type,
            "question_data": q.question_data,  # Contains options but not correct answer
            "difficulty": q.difficulty
        }
        for q in quizzes
    ]


@router.post("/sessions/{session_id}/submit", response_model=QuizAttemptResponse)
def submit_quiz_answer(
    session_id: int,
    answer_data: QuizAnswerSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Submit an answer for a quiz question.
    Returns immediate feedback (correct/incorrect) and explanation.
    
    ## Request Body Structure
    
    The `user_answer` field structure depends on the question type:
    
    ### Multiple Choice
    ```json
    {
        "quiz_id": 1,
        "user_answer": {
            "selected_id": "option_a"
        },
        "time_spent": 30
    }
    ```
    - `selected_id`: The ID of the selected option
    
    ### True/False
    ```json
    {
        "quiz_id": 2,
        "user_answer": {
            "answer": true
        },
        "time_spent": 15
    }
    ```
    - `answer`: Boolean value (true or false)
    
    ### Matching
    ```json
    {
        "quiz_id": 3,
        "user_answer": {
            "matches": {
                "term_1": "definition_a",
                "term_2": "definition_b",
                "term_3": "definition_c"
            }
        },
        "time_spent": 60
    }
    ```
    - `matches`: Object mapping term IDs to definition IDs
    
    ## Response
    Returns the graded attempt with correct answer and explanation.
    """
    # Verify session
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id,
        QuizSession.user_id == current_user.id  # type: ignore
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    if session.status != "in_progress":  # type: ignore
        raise HTTPException(status_code=400, detail="Quiz session is not active")
    
    # Get quiz
    quiz = db.query(Quiz).filter(Quiz.id == answer_data.quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Check if already answered
    existing_attempt = db.query(QuizAttempt).filter(
        QuizAttempt.session_id == session_id,
        QuizAttempt.quiz_id == answer_data.quiz_id
    ).first()
    
    if existing_attempt:
        raise HTTPException(status_code=400, detail="Question already answered in this session")
    
    # Grade the answer
    is_correct = _grade_answer(quiz, answer_data.user_answer)
    
    # Create attempt record
    attempt = QuizAttempt(
        session_id=session_id,
        quiz_id=answer_data.quiz_id,
        user_id=current_user.id,  # type: ignore
        user_answer=answer_data.user_answer,
        is_correct=is_correct,
        time_spent=answer_data.time_spent
    )
    db.add(attempt)
    
    # Update session stats
    if is_correct:
        session.correct_answers += 1  # type: ignore
    
    db.commit()
    db.refresh(attempt)
    
    return QuizAttemptResponse(
        attempt_id=attempt.id,  # type: ignore
        quiz_id=quiz.id,  # type: ignore
        is_correct=is_correct,# type: ignore
        user_answer=answer_data.user_answer,# type: ignore
        correct_answer=quiz.question_data,  # Contains correct answer # type: ignore
        explanation=quiz.explanation,  # type: ignore
        question=quiz.question,  # type: ignore
        question_type=quiz.question_type  # type: ignore
    )


@router.post("/sessions/{session_id}/complete", response_model=QuizSessionResult)
def complete_quiz_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Complete a quiz session and get final results.
    """
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id,
        QuizSession.user_id == current_user.id  # type: ignore
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    if session.status == "completed":  # type: ignore
        raise HTTPException(status_code=400, detail="Quiz session already completed")
    
    # Get all attempts
    attempts = db.query(QuizAttempt).filter(QuizAttempt.session_id == session_id).all()
    
    # Calculate score
    total = len(attempts)
    correct = sum(1 for a in attempts if a.is_correct)  # type: ignore
    score_percentage = (correct / total * 100) if total > 0 else 0
    
    # Update session
    session.status = "completed"  # type: ignore
    session.score_percentage = score_percentage  # type: ignore
    session.completed_at = func.now()  # type: ignore
    
    db.commit()
    db.refresh(session)
    
    # Format attempts for response
    attempt_responses = []
    for attempt in attempts:
        quiz = db.query(Quiz).filter(Quiz.id == attempt.quiz_id).first()
        attempt_responses.append(QuizAttemptResponse(
            attempt_id=attempt.id,  # type: ignore
            quiz_id=attempt.quiz_id,# type: ignore
            is_correct=attempt.is_correct,# type: ignore
            user_answer=attempt.user_answer,# type: ignore
            correct_answer=quiz.question_data if quiz else {},# type: ignore
            explanation=quiz.explanation if quiz else None,# type: ignore
            question=quiz.question if quiz else "",# type: ignore
            question_type=quiz.question_type if quiz else ""# type: ignore
        ))
    
    return QuizSessionResult(
        session_id=session.id,  # type: ignore
        total_questions=total,
        correct_answers=correct,
        incorrect_answers=total - correct,
        score_percentage=score_percentage,
        completed_at=session.completed_at,  # type: ignore
        attempts=attempt_responses
    )


@router.get("/sessions/{session_id}/results", response_model=QuizSessionResult)
def get_quiz_results(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get results for a completed quiz session.
    """
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id,
        QuizSession.user_id == current_user.id  # type: ignore
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    if session.status != "completed":  # type: ignore
        raise HTTPException(status_code=400, detail="Quiz session not completed yet")
    
    # Get all attempts
    attempts = db.query(QuizAttempt).filter(QuizAttempt.session_id == session_id).all()
    
    # Format response
    attempt_responses = []
    for attempt in attempts:
        quiz = db.query(Quiz).filter(Quiz.id == attempt.quiz_id).first()
        attempt_responses.append(QuizAttemptResponse(
            attempt_id=attempt.id,  # type: ignore
            quiz_id=attempt.quiz_id,# type: ignore
            is_correct=attempt.is_correct,# type: ignore
            user_answer=attempt.user_answer,# type: ignore
            correct_answer=quiz.question_data if quiz else {},# type: ignore
            explanation=quiz.explanation if quiz else None,# type: ignore
            question=quiz.question if quiz else "",# type: ignore
            question_type=quiz.question_type if quiz else ""# type: ignore
        ))
    
    return QuizSessionResult(
        session_id=session.id,  # type: ignore
        total_questions=session.total_questions,# type: ignore
        correct_answers=session.correct_answers,# type: ignore
        incorrect_answers=session.total_questions - session.correct_answers,# type: ignore
        score_percentage=session.score_percentage,# type: ignore
        completed_at=session.completed_at,  # type: ignore
        attempts=attempt_responses
    )


@router.get("/history", response_model=List[QuizSessionResponse])
def get_quiz_history(
    course_id: Optional[int] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get user's quiz session history.
    Optionally filter by course_id.
    """
    query = db.query(QuizSession).filter(QuizSession.user_id == current_user.id)  # type: ignore
    
    if course_id:
        query = query.filter(QuizSession.course_id == course_id)
    
    sessions = query.order_by(QuizSession.started_at.desc()).limit(limit).all()
    
    return sessions


# ============= Helper Functions =============

def _grade_answer(quiz: Quiz, user_answer: Dict[str, Any]) -> bool:
    """
    Grade a quiz answer based on question type.
    """
    question_type = quiz.question_type
    correct_data = quiz.question_data
    
    if question_type == "multiple_choice":# type: ignore
        # Compare selected option ID
        return user_answer.get("selected_id") == correct_data.get("correct_answer_id")
    
    elif question_type == "true_false":# type: ignore
        # Compare boolean value
        return user_answer.get("answer") == correct_data.get("correct_boolean")
    
    elif question_type == "matching":# type: ignore
        # Compare matching pairs
        user_matches = user_answer.get("matches", {})
        correct_matches = correct_data.get("correct_matches", {})
        return user_matches == correct_matches
    
    elif question_type == "short_answer":# type: ignore
        # Simple string comparison (case-insensitive)
        user_text = str(user_answer.get("answer", "")).strip().lower()
        correct_text = str(correct_data.get("correct_answer", "")).strip().lower()
        return user_text == correct_text
    
    return False
