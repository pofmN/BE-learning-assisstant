"""
API endpoints for quiz interactions - taking quizzes, reviewing results, etc.
"""
import json
import logging
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
logger = logging.getLogger(__name__)


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
    started_at: datetime
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

@router.get("/sections/{section_id}/quizzes", response_model=List[Dict[str, Any]])
def get_section_quizzes(
    section_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all quizzes for a specific course section.
    Returns quizzes with correct answers.
    """
    # Verify section exists and user has access
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Course section not found")
    
    # Get quizzes
    query = db.query(Quiz).filter(Quiz.section_id == section_id)
    
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
        session_type="section" if session_data.section_id else "regular",
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
    
    Supports both regular quiz sessions and LLM-generated review quizzes.
    """
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id,
        QuizSession.user_id == current_user.id  # type: ignore
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    # Check if this is a final_review with generated questions
    if session.session_type == "final_review" and session.generated_questions:  # type: ignore
        try:
            generated_questions = json.loads(session.generated_questions)  # type: ignore
            
            # Return generated questions without correct answers
            questions_for_user = []
            for i, q in enumerate(generated_questions):
                question_data = dict(q.get("question_data", {}))
                
                # Remove correct answer from question_data
                if "correct_answer" in question_data:
                    del question_data["correct_answer"]
                if "correct_matches" in question_data:
                    del question_data["correct_matches"]
                if "acceptable_answers" in question_data:
                    del question_data["acceptable_answers"]
                
                questions_for_user.append({
                    "quiz_id": i,  # Use index as temporary quiz_id
                    "question": q.get("question"),
                    "question_type": q.get("question_type"),
                    "question_data": question_data,
                    "difficulty": q.get("difficulty"),
                    "is_generated": True  # Flag to indicate this is a generated question
                })
            
            return questions_for_user
            
        except Exception as e:
            logger.error(f"Error parsing generated questions: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error loading generated questions"
            )
    
    # Regular quiz session - get from database
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
            "difficulty": q.difficulty,
            "is_generated": False
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
    
    # Check if this is a generated quiz
    if session.session_type == "final_review" and session.generated_questions:  # type: ignore
        # Handle generated question
        try:
            generated_questions = json.loads(session.generated_questions)  # type: ignore
            quiz_index = answer_data.quiz_id  # quiz_id is actually the index
            
            if quiz_index >= len(generated_questions):
                raise HTTPException(status_code=404, detail="Question not found")
            
            quiz_data = generated_questions[quiz_index]
            
            # Check if already answered
            existing_attempt = db.query(QuizAttempt).filter(
                QuizAttempt.session_id == session_id,
                QuizAttempt.quiz_id == quiz_index  # Store index as quiz_id
            ).first()
            
            if existing_attempt:
                raise HTTPException(status_code=400, detail="Question already answered in this session")
            
            # Grade the answer using generated question data
            is_correct = _grade_generated_answer(quiz_data, answer_data.user_answer)
            
            # Create attempt record (quiz_id stores the index)
            attempt = QuizAttempt(
                session_id=session_id,
                quiz_id=quiz_index,  # Store index
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
                quiz_id=quiz_index,
                is_correct=is_correct,
                user_answer=answer_data.user_answer,
                correct_answer=quiz_data.get("question_data", {}),
                explanation=quiz_data.get("explanation", ""),
                question=quiz_data.get("question", ""),
                question_type=quiz_data.get("question_type", "")
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing generated questions: {e}")
            raise HTTPException(status_code=500, detail="Error loading quiz questions")
    
    # Regular quiz (from database)
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
    total_questions = session.total_questions  # Use the total number of questions in the session
    correct = sum(1 for a in attempts if a.is_correct)  # type: ignore
    score_percentage = (correct / total_questions * 100) if total_questions > 0 else 0 # type: ignore
    
    # Update session
    session.status = "completed"  # type: ignore
    session.score_percentage = score_percentage  # type: ignore
    session.completed_at = func.now()  # type: ignore
    
    db.commit()
    db.refresh(session)
    
    # Trigger analysis generation for final review quiz
    if str(session.session_type) == "final_review":  # type: ignore
        from app.api.v1.review_quiz import generate_review_analysis
        try:
            generate_review_analysis(
                session_id=session_id,
                user_id=int(current_user.id),  # type: ignore
                course_id=int(session.course_id),  # type: ignore
                db=db
            )
        except Exception as e:
            # Log but don't fail the completion
            import logging
            logging.getLogger(__name__).error(f"Failed to generate review analysis: {e}")
    
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
        total_questions=total_questions, # type: ignore
        correct_answers=correct,
        incorrect_answers=total_questions - correct, # type: ignore
        score_percentage=score_percentage, # type: ignore
        started_at=session.started_at,  # type: ignore
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
        started_at=session.started_at,  # type: ignore
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
        return user_answer.get("answer") == correct_data.get("correct_answer")
    
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


def _grade_generated_answer(quiz_data: Dict[str, Any], user_answer: Dict[str, Any]) -> bool:
    """
    Grade a generated quiz answer based on question type.
    Similar to _grade_answer but works with dictionary data instead of Quiz model.
    """
    question_type = quiz_data.get("question_type")
    correct_data = quiz_data.get("question_data", {})
    
    if question_type == "multiple_choice":
        # Compare selected option ID
        user_selected = user_answer.get("selected_id")
        correct_answer = correct_data.get("correct_answer")
        return user_selected == correct_answer
    
    elif question_type == "true_false":
        # Compare boolean value
        user_bool = user_answer.get("answer")
        correct_bool = correct_data.get("correct_answer")
        return user_bool == correct_bool
    
    elif question_type == "matching":
        # Compare matching pairs
        user_matches = user_answer.get("matches", {})
        correct_matches = correct_data.get("correct_matches", {})
        return user_matches == correct_matches
    
    elif question_type == "short_answer":
        # Check against correct answer and acceptable answers
        user_text = str(user_answer.get("answer", "")).strip().lower()
        correct_text = str(correct_data.get("correct_answer", "")).strip().lower()
        
        if user_text == correct_text:
            return True
        
        # Check acceptable alternatives
        acceptable_answers = correct_data.get("acceptable_answers", [])
        for acceptable in acceptable_answers:
            if user_text == str(acceptable).strip().lower():
                return True
        
        return False
    
    return False
