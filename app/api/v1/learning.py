"""
Personalized learning endpoints.
"""
from typing import Any, List
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dependencies import get_current_active_user, get_db
from app.models.learning import LearningProgress
from app.models.test import TestAnswer, TestResult
from app.models.mcq import MCQ
from app.models.user import User
from app.schemas.learning import (
    LearningProgress as LearningProgressSchema,
    TopicRecommendation,
    WeakArea,
)

router = APIRouter()


@router.get("/progress", response_model=List[LearningProgressSchema])
def get_learning_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get user's learning progress across all topics.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of learning progress records
    """
    # Update progress from test results
    _update_learning_progress(db, current_user.id) # type: ignore

    # Get progress records
    progress = (
        db.query(LearningProgress)
        .filter(LearningProgress.user_id == current_user.id)
        .order_by(LearningProgress.last_studied.desc())
        .all()
    )

    return progress


@router.get("/recommendations", response_model=List[TopicRecommendation])
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get personalized topic recommendations.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of recommended topics
    """
    # Update progress first
    _update_learning_progress(db, current_user.id) # type: ignore

    progress = (
        db.query(LearningProgress)
        .filter(LearningProgress.user_id == current_user.id)
        .all()
    )

    recommendations = []

    # Recommend weak topics (accuracy < 60%)
    weak_topics = [p for p in progress if p.accuracy < 60 and p.total_attempts >= 3] # type: ignore
    for topic_progress in weak_topics:
        recommendations.append(
            {
                "topic": topic_progress.topic,
                "reason": f"Your accuracy is {topic_progress.accuracy:.1f}%. Practice more to improve!",
                "priority": "high",
            }
        )

    # Recommend topics with few attempts
    new_topics = [p for p in progress if p.total_attempts < 3] # type: ignore
    for topic_progress in new_topics:
        recommendations.append(
            {
                "topic": topic_progress.topic,
                "reason": "You haven't practiced this topic much. Try more questions!",
                "priority": "medium",
            }
        )

    # Recommend strong topics for review (accuracy > 80%)
    strong_topics = [p for p in progress if p.accuracy > 80 and p.total_attempts >= 5] # type: ignore
    for topic_progress in strong_topics[:2]:  # Limit to 2
        recommendations.append(
            {
                "topic": topic_progress.topic,
                "reason": f"Great job! Keep practicing to maintain your {topic_progress.accuracy:.1f}% accuracy.",
                "priority": "low",
            }
        )

    # If no progress, recommend getting started
    if not recommendations:
        recommendations.append(
            {
                "topic": "General",
                "reason": "Start your learning journey by taking some tests!",
                "priority": "high",
            }
        )

    return recommendations


@router.get("/weak-areas", response_model=List[WeakArea])
def get_weak_areas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get analysis of weak areas.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of weak areas with suggestions
    """
    # Update progress first
    _update_learning_progress(db, current_user.id) # type: ignore

    progress = (
        db.query(LearningProgress)
        .filter(LearningProgress.user_id == current_user.id)
        .filter(LearningProgress.accuracy < 70)
        .filter(LearningProgress.total_attempts >= 3)
        .order_by(LearningProgress.accuracy)
        .limit(5)
        .all()
    )

    weak_areas = []
    for topic_progress in progress:
        suggestions = _generate_suggestions(topic_progress.accuracy) # type: ignore
        weak_areas.append(
            {
                "topic": topic_progress.topic,
                "accuracy": topic_progress.accuracy,
                "total_attempts": topic_progress.total_attempts,
                "suggestions": suggestions,
            }
        )

    return weak_areas


def _update_learning_progress(db: Session, user_id: int) -> None:
    """
    Update learning progress based on test results.

    Args:
        db: Database session
        user_id: User ID
    """
    # Get all test answers with topics
    test_answers = (
        db.query(TestAnswer, MCQ.topic)
        .join(MCQ, TestAnswer.mcq_id == MCQ.id)
        .join(TestResult, TestAnswer.test_result_id == TestResult.id)
        .filter(TestResult.user_id == user_id)
        .filter(MCQ.topic.isnot(None))
        .all()
    )

    # Aggregate by topic
    topic_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    for answer, topic in test_answers:
        topic_stats[topic]["total"] += 1
        if answer.is_correct:
            topic_stats[topic]["correct"] += 1

    # Update or create progress records
    for topic, stats in topic_stats.items():
        progress = (
            db.query(LearningProgress)
            .filter(
                LearningProgress.user_id == user_id,
                LearningProgress.topic == topic,
            )
            .first()
        )

        accuracy = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0

        if progress:
            progress.total_attempts = stats["total"] # type: ignore
            progress.correct_attempts = stats["correct"] # type: ignore
            progress.accuracy = accuracy # type: ignore
        else:
            progress = LearningProgress(
                user_id=user_id,
                topic=topic,
                total_attempts=stats["total"],
                correct_attempts=stats["correct"],
                accuracy=accuracy,
            )
            db.add(progress)

    db.commit()


def _generate_suggestions(accuracy: float) -> List[str]:
    """
    Generate suggestions based on accuracy.

    Args:
        accuracy: Accuracy percentage

    Returns:
        List of suggestions
    """
    if accuracy < 40:
        return [
            "Review the fundamental concepts of this topic",
            "Start with easier questions to build confidence",
            "Consider reading additional materials or watching tutorial videos",
            "Practice regularly, even if just 10-15 minutes per day",
        ]
    elif accuracy < 60:
        return [
            "Focus on understanding why you got questions wrong",
            "Try explaining the concepts to someone else",
            "Review your incorrect answers and their explanations",
            "Practice more questions on this topic",
        ]
    else:
        return [
            "You're doing well! Keep practicing to improve further",
            "Try more challenging questions on this topic",
            "Review edge cases and tricky scenarios",
            "Help others understand this topic to reinforce your knowledge",
        ]
