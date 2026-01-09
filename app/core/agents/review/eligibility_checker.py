"""
Eligibility checker for final review quiz.
Verifies user has completed all quizzes in the course.
"""
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.course import Course, Quiz
from app.models.quiz_attempt import QuizSession, QuizAttempt
from app.core.agents.review.schemas import EligibilityResponse, CourseCompletionStatus

logger = logging.getLogger(__name__)


class EligibilityChecker:
    """
    Checks if user is eligible to take final review quiz.
    Requirements: Must have attempted all quizzes in the course at least once.
    """

    def __init__(self, db: Session):
        self.db = db

    def check_eligibility(self, user_id: int, course_id: int) -> EligibilityResponse:
        """
        Check if user is eligible for final review quiz.

        Args:
            user_id: User ID
            course_id: Course ID

        Returns:
            EligibilityResponse with eligibility status and completion details
        """
        try:
            # Get course
            course = self.db.query(Course).filter(Course.id == course_id).first()
            if not course:
                return EligibilityResponse(
                    eligible=False,
                    course_completion=CourseCompletionStatus(
                        total_sections=0,
                        completed_sections=0,
                        total_quizzes=0,
                        attempted_quizzes=0,
                        completion_percentage=0.0
                    ),
                    message="Course not found"
                )

            # Count total quizzes in course
            total_quizzes = self.db.query(Quiz).filter(
                Quiz.course_id == course_id,
                Quiz.session_id.is_(None)  # Only count original learning quizzes
            ).count()

            if total_quizzes == 0:
                return EligibilityResponse(
                    eligible=False,
                    course_completion=CourseCompletionStatus(
                        total_sections=0,
                        completed_sections=0,
                        total_quizzes=0,
                        attempted_quizzes=0,
                        completion_percentage=0.0
                    ),
                    message="No quizzes available in this course"
                )

            # Count unique quizzes user has attempted (exclude final review sessions)
            attempted_quiz_ids = self.db.query(QuizAttempt.quiz_id).join(
                QuizSession, QuizSession.id == QuizAttempt.session_id
            ).join(
                Quiz, Quiz.id == QuizAttempt.quiz_id
            ).filter(
                QuizSession.user_id == user_id,
                QuizSession.course_id == course_id,
                QuizSession.session_type != "final_review",  # Exclude final review sessions
                Quiz.session_id.is_(None)  # Only count attempts on original quizzes
            ).distinct().all()

            attempted_count = len(attempted_quiz_ids)
            completion_percentage = (attempted_count / total_quizzes * 100) if total_quizzes > 0 else 0

            # Check for existing incomplete review session
            existing_review = self.db.query(QuizSession).filter(
                QuizSession.user_id == user_id,
                QuizSession.course_id == course_id,
                QuizSession.session_type == "final_review",
                QuizSession.status == "in_progress"
            ).first()

            existing_review_data = None
            if existing_review:
                # Count how many questions already answered
                answered_count = self.db.query(QuizAttempt).filter(
                    QuizAttempt.session_id == existing_review.id  # type: ignore
                ).count()
                
                existing_review_data = {
                    "session_id": int(existing_review.id),  # type: ignore
                    "status": str(existing_review.status),  # type: ignore
                    "answered": answered_count,
                    "total": int(existing_review.total_questions)  # type: ignore
                }

            # Count sections (optional - for display purposes)
            total_sections = self.db.query(func.count(func.distinct(Quiz.section_id))).filter(
                Quiz.course_id == course_id,
                Quiz.section_id.isnot(None)
            ).scalar() or 0

            # Determine eligibility
            is_eligible = attempted_count >= total_quizzes
            
            if existing_review_data:
                message = f"You have an incomplete review quiz ({existing_review_data['answered']}/{existing_review_data['total']} answered). Resume or start new."
            elif is_eligible:
                message = "You're eligible for final review quiz!"
            else:
                remaining = total_quizzes - attempted_count
                message = f"Complete {remaining} more quiz{'zes' if remaining != 1 else ''} to unlock final review."

            return EligibilityResponse(
                eligible=is_eligible,
                course_completion=CourseCompletionStatus(
                    total_sections=total_sections,
                    completed_sections=total_sections,  # Assuming sections complete if all quizzes done
                    total_quizzes=total_quizzes,
                    attempted_quizzes=attempted_count,
                    completion_percentage=round(completion_percentage, 2)
                ),
                existing_review=existing_review_data,
                message=message
            )

        except Exception as e:
            logger.error(f"Error checking eligibility: {e}")
            raise
