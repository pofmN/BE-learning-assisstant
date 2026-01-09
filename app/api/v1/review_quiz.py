"""
API endpoints for final review quiz functionality.
"""
import logging
import json
from typing import Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.user import User
from app.models.course import Course, Quiz
from app.models.quiz_attempt import QuizSession
from app.models.review_analysis import ReviewQuizAnalysis
from app.core.agents.review import (
    EligibilityChecker,
    QuizSelector,
    QuizGenerator,
    PerformanceAnalyzer,
    RecommendationGenerator
)
from app.core.agents.review.schemas import (
    EligibilityResponse,
    ReviewQuizGenerateResponse,
    QuestionDistribution,
    ReviewInsightsResponse,
    PerformanceSummary,
    PerformanceBreakdown,
    TopicPerformance,
    Recommendation,
    NextSteps
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# Request schemas
class ReviewQuizGenerateRequest(BaseModel):
    """Request to generate review quiz."""
    strategy: str = "balanced"  # balanced, weak_focus, comprehensive
    question_count: int = 30


# ============= Endpoints =============

@router.get("/courses/{course_id}/final-review/eligibility", response_model=EligibilityResponse)
def check_review_eligibility(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Check if user is eligible to take final review quiz.
    
    Requirements:
    - Must have attempted all quizzes in the course at least once
    
    Also returns information about any incomplete review session.
    """
    try:
        checker = EligibilityChecker(db)
        result = checker.check_eligibility(
            user_id=int(current_user.id),  # type: ignore
            course_id=course_id
        )
        return result
        
    except Exception as e:
        logger.error(f"Error checking eligibility: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check eligibility: {str(e)}"
        )


@router.post("/courses/{course_id}/final-review/generate", response_model=ReviewQuizGenerateResponse)
def generate_review_quiz(
    course_id: int,
    request: ReviewQuizGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Generate a final review quiz for the course.
    
    Strategies:
    - **balanced** (default): 40% weak, 40% medium, 20% strong topics
    - **weak_focus**: 70% weak topics, 30% medium/strong (for focused improvement)
    - **comprehensive**: Even distribution across all sections
    
    The quiz is automatically saved as a resumable session.
    User can continue where they left off if interrupted.
    """
    try:
        user_id = int(current_user.id)  # type: ignore
        
        # Check eligibility
        checker = EligibilityChecker(db)
        eligibility = checker.check_eligibility(user_id, course_id)
        
        if not eligibility.eligible:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=eligibility.message
            )
        
        # Check for existing incomplete review
        if eligibility.existing_review:
            return ReviewQuizGenerateResponse(
                session_id=eligibility.existing_review["session_id"],
                total_questions=eligibility.existing_review["total"],
                selection_strategy=request.strategy,
                question_distribution=QuestionDistribution(
                    weak_topics=0,
                    medium_topics=0,
                    strong_topics=0
                ),
                message=f"Resuming existing review quiz: {eligibility.existing_review['answered']}/{eligibility.existing_review['total']} completed"
            )
        
        # Verify course exists
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Select example quizzes based on performance
        selector = QuizSelector(db)
        example_quizzes, distribution = selector.select_questions_for_generation(
            user_id=user_id,
            course_id=course_id,
            strategy=request.strategy,
            question_count=request.question_count
        )
        
        # Generate new questions based on examples
        generator = QuizGenerator(db)
        generated_questions = generator.generate_questions(
            example_quizzes=example_quizzes,
            question_count=request.question_count
        )
        
        logger.info(f"Generated {len(generated_questions)} new questions for review quiz")
        
        # Create quiz session first (with generated_questions JSON)
        quiz_session = QuizSession(
            user_id=user_id,
            course_id=course_id,
            section_id=None,  # Final review covers entire course
            session_type="final_review",
            generated_questions=json.dumps(generated_questions),
            total_questions=len(generated_questions),
            status="in_progress"
        )
        db.add(quiz_session)
        db.flush()  # Get session.id without committing
        
        # Save generated questions to Quiz table with session_id
        saved_quiz_ids = []
        for q_data in generated_questions:
            quiz = Quiz(
                course_id=course_id,
                section_id=None,  # Final review questions not tied to specific section
                session_id=quiz_session.id,  # Link to session - marks as generated quiz
                question=q_data.get("question", ""),
                question_type=q_data.get("question_type", "multiple_choice"),
                question_data=q_data.get("question_data", {}),
                explanation=q_data.get("explanation"),
                difficulty=q_data.get("difficulty")
            )
            db.add(quiz)
            db.flush()
            saved_quiz_ids.append(quiz.id)
        
        db.commit()
        db.refresh(quiz_session)
        
        logger.info(
            f"Generated final review quiz for user {user_id}, course {course_id}, "
            f"session {quiz_session.id}, {len(generated_questions)} questions"
        )
        
        return ReviewQuizGenerateResponse(
            session_id=int(quiz_session.id),  # type: ignore
            total_questions=len(generated_questions),
            selection_strategy=request.strategy,
            question_distribution=QuestionDistribution(**distribution),
            message="Final review quiz generated successfully. Start when ready!"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating review quiz: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate review quiz: {str(e)}"
        )


@router.get("/courses/{course_id}/final-review/insights", response_model=ReviewInsightsResponse)
def get_review_insights(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get detailed insights and recommendations from the most recent final review quiz.
    
    Returns:
    - Performance comparison (original vs review)
    - Question-level breakdown (improved, regressed, etc.)
    - Topic/section analysis
    - Personalized study recommendations
    - Next steps and suggested study plan
    
    This endpoint is automatically called after completing a final review quiz.
    """
    try:
        user_id = int(current_user.id)  # type: ignore
        
        # Get most recent review analysis for this course
        analysis = db.query(ReviewQuizAnalysis).filter(
            ReviewQuizAnalysis.user_id == user_id,
            ReviewQuizAnalysis.course_id == course_id
        ).order_by(ReviewQuizAnalysis.analysis_generated_at.desc()).first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No review quiz analysis found. Complete a final review quiz first."
            )
        
        # Parse stored JSON data
        topic_breakdown_data = json.loads(analysis.topic_breakdown) if analysis.topic_breakdown else []  # type: ignore
        recommendations_data = json.loads(analysis.recommendations) if analysis.recommendations else []  # type: ignore
        insights_data = json.loads(analysis.insights) if analysis.insights else {}  # type: ignore
        
        # Build response
        performance_summary = PerformanceSummary(
            original_avg_score=float(analysis.original_avg_score),  # type: ignore
            review_score=float(analysis.review_score),  # type: ignore
            improvement=float(analysis.improvement_percentage),  # type: ignore
            grade=insights_data.get("grade", "N/A")
        )
        
        question_breakdown = PerformanceBreakdown(
            improved=int(analysis.improved_count),  # type: ignore
            regressed=int(analysis.regressed_count),  # type: ignore
            persistent_weak=int(analysis.persistent_weak_count),  # type: ignore
            consistent_strong=int(analysis.consistent_strong_count)  # type: ignore
        )
        
        topic_analysis = [
            TopicPerformance(**topic_data)
            for topic_data in topic_breakdown_data
        ]
        
        recommendations = [
            Recommendation(**rec_data)
            for rec_data in recommendations_data
        ]
        
        next_steps_data = insights_data.get("next_steps", {})
        next_steps = NextSteps(
            weak_topics=next_steps_data.get("weak_topics", []),
            suggested_study_time=next_steps_data.get("suggested_study_time", "2-3 hours"),
            review_again_after=next_steps_data.get("review_again_after", "7 days"),
            confidence_level=next_steps_data.get("confidence_level", "medium")
        )
        
        return ReviewInsightsResponse(
            analysis_id=int(analysis.id),  # type: ignore
            review_session_id=int(analysis.review_session_id),  # type: ignore
            completion_date=analysis.analysis_generated_at,  # type: ignore
            performance_summary=performance_summary,
            question_breakdown=question_breakdown,
            topic_analysis=topic_analysis,
            recommendations=recommendations,
            next_steps=next_steps
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting review insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get review insights: {str(e)}"
        )


# Helper function to generate analysis (called from quiz.py after completion)
def generate_review_analysis(
    session_id: int,
    user_id: int,
    course_id: int,
    db: Session
):
    """
    Generate analysis and recommendations for completed final review quiz.
    Called automatically when review quiz is completed.
    """
    try:
        logger.info(f"Generating analysis for review session {session_id}")
        
        # Analyze performance
        analyzer = PerformanceAnalyzer(db)
        performance_report = analyzer.analyze_performance(
            user_id=user_id,
            course_id=course_id,
            review_session_id=session_id
        )
        
        # Calculate scores
        session = db.query(QuizSession).filter(QuizSession.id == session_id).first()
        review_score = float(session.score_percentage) if session else 0.0  # type: ignore
        
        # Calculate original average score
        original_sessions = db.query(QuizSession).filter(
            QuizSession.user_id == user_id,
            QuizSession.course_id == course_id,
            QuizSession.session_type.in_(["regular", "section"]),
            QuizSession.status == "completed"
        ).all()
        
        if original_sessions:
            original_avg_score = sum(
                float(s.score_percentage) for s in original_sessions  # type: ignore
            ) / len(original_sessions)
        else:
            original_avg_score = 0.0
        
        improvement = review_score - original_avg_score
        
        # Generate recommendations using LLM
        recommender = RecommendationGenerator(db)
        recommendation_data = recommender.generate_recommendations(
            course_id=course_id,
            performance_report=performance_report,
            original_score=original_avg_score,
            review_score=review_score
        )
        
        # Format topic breakdown for storage
        topic_breakdown_list = []
        for topic, data in performance_report.topic_analysis.items():
            improvement_val = data.get("improvement", 0)
            status = "improving" if improvement_val > 10 else "regression" if improvement_val < -10 else "stable"
            
            topic_breakdown_list.append({
                "section": topic,
                "section_id": data.get("section_id"),
                "original_score": round(data.get("original_score", 0), 1),
                "review_score": round(data.get("review_score", 0), 1),
                "improvement": round(improvement_val, 1),
                "status": status
            })
        
        # Store analysis
        analysis = ReviewQuizAnalysis(
            user_id=user_id,
            course_id=course_id,
            review_session_id=session_id,
            total_original_attempts=len(original_sessions),
            original_avg_score=round(original_avg_score, 2),
            review_score=round(review_score, 2),
            improvement_percentage=round(improvement, 2),
            improved_count=len(performance_report.improved_questions),
            regressed_count=len(performance_report.regressed_questions),
            persistent_weak_count=len(performance_report.persistent_weaknesses),
            consistent_strong_count=len(performance_report.consistent_strengths),
            topic_breakdown=json.dumps(topic_breakdown_list),
            recommendations=json.dumps(recommendation_data["recommendations"]),
            insights=json.dumps({
                "grade": recommendation_data["grade"],
                "next_steps": recommendation_data["next_steps"],
                "motivation_message": recommendation_data.get("motivation_message", "")
            })
        )
        
        db.add(analysis)
        db.commit()
        
        logger.info(f"Successfully generated analysis for review session {session_id}")
        
    except Exception as e:
        logger.error(f"Error generating review analysis: {e}")
        db.rollback()
        # Don't raise - analysis generation failure shouldn't block quiz completion
