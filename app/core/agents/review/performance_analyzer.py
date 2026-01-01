"""
Performance analyzer for final review quiz.
Compares original attempts with review attempts and generates insights.
"""
import logging
from typing import Dict, List
from sqlalchemy.orm import Session

from app.models.quiz_attempt import QuizAttempt, QuizSession
from app.models.course import Quiz, CourseSection
from app.core.agents.review.schemas import PerformanceReport

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """
    Analyzes performance by comparing original quiz attempts with review quiz attempts.
    Identifies improvements, regressions, and persistent weaknesses.
    """

    def __init__(self, db: Session):
        self.db = db

    def analyze_performance(
        self,
        user_id: int,
        course_id: int,
        review_session_id: int
    ) -> PerformanceReport:
        """
        Analyze user's performance comparing original attempts with review attempts.

        Args:
            user_id: User ID
            course_id: Course ID
            review_session_id: Review quiz session ID

        Returns:
            PerformanceReport with detailed analysis
        """
        try:
            # Get review session attempts
            review_attempts = self.db.query(QuizAttempt).filter(
                QuizAttempt.session_id == review_session_id
            ).all()

            if not review_attempts:
                raise ValueError(f"No attempts found for review session {review_session_id}")

            # Build quiz_id -> review_result mapping
            review_results = {}
            for attempt in review_attempts:
                quiz_id = int(attempt.quiz_id)  # type: ignore
                review_results[quiz_id] = {
                    "correct": bool(attempt.is_correct),  # type: ignore
                    "quiz": attempt.quiz
                }

            # Get original attempts for these same quizzes
            quiz_ids = list(review_results.keys())
            original_attempts = self.db.query(QuizAttempt).join(
                QuizSession, QuizSession.id == QuizAttempt.session_id
            ).filter(
                QuizSession.user_id == user_id,
                QuizSession.course_id == course_id,
                QuizSession.session_type.in_(["regular", "section"]),  # Exclude reviews
                QuizAttempt.quiz_id.in_(quiz_ids)
            ).all()

            # Build quiz_id -> original performance mapping (most recent attempt)
            original_performance = {}
            for attempt in original_attempts:
                quiz_id = int(attempt.quiz_id)  # type: ignore
                # Keep most recent attempt (later attempts override)
                original_performance[quiz_id] = bool(attempt.is_correct)  # type: ignore

            # Categorize questions
            improved = []
            regressed = []
            persistent_weak = []
            consistent_strong = []

            for quiz_id, review_data in review_results.items():
                review_correct = review_data["correct"]
                original_correct = original_performance.get(quiz_id, False)  # Default to wrong if no original

                if not original_correct and review_correct:
                    improved.append(quiz_id)
                elif original_correct and not review_correct:
                    regressed.append(quiz_id)
                elif not original_correct and not review_correct:
                    persistent_weak.append(quiz_id)
                else:  # Both correct
                    consistent_strong.append(quiz_id)

            # Calculate improvement rate
            improvement_rate = (len(improved) / len(review_results) * 100) if review_results else 0

            # Topic/Section analysis
            topic_analysis = self._analyze_by_topic(
                review_results,
                original_performance,
                improved,
                persistent_weak
            )

            # Identify weak and strong topics
            weak_topics = [
                topic for topic, data in topic_analysis.items()
                if data.get("review_score", 0) < 60
            ]
            strong_topics = [
                topic for topic, data in topic_analysis.items()
                if data.get("review_score", 0) >= 80
            ]

            logger.info(
                f"Performance analysis: {len(improved)} improved, {len(regressed)} regressed, "
                f"{len(persistent_weak)} persistent weak, {len(consistent_strong)} strong"
            )

            return PerformanceReport(
                improved_questions=improved,
                regressed_questions=regressed,
                persistent_weaknesses=persistent_weak,
                consistent_strengths=consistent_strong,
                improvement_rate=round(improvement_rate, 2),
                topic_analysis=topic_analysis,
                weak_topics=weak_topics,
                strong_topics=strong_topics
            )

        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            raise

    def _analyze_by_topic(
        self,
        review_results: Dict,
        original_performance: Dict,
        improved: List[int],
        persistent_weak: List[int]
    ) -> Dict[str, Dict]:
        """
        Analyze performance grouped by topic/section.

        Returns:
            Dict mapping topic name to performance metrics
        """
        topic_data = {}

        for quiz_id, review_data in review_results.items():
            quiz = review_data["quiz"]
            
            # Get section name (topic)
            if quiz.section:  # type: ignore
                topic = str(quiz.section.title)  # type: ignore
                section_id = int(quiz.section.id)  # type: ignore
            else:
                topic = "General"
                section_id = None

            if topic not in topic_data:
                topic_data[topic] = {
                    "section_id": section_id,
                    "original_correct": 0,
                    "original_total": 0,
                    "review_correct": 0,
                    "review_total": 0
                }

            # Count original performance
            if quiz_id in original_performance:
                topic_data[topic]["original_total"] += 1
                if original_performance[quiz_id]:
                    topic_data[topic]["original_correct"] += 1

            # Count review performance
            topic_data[topic]["review_total"] += 1
            if review_data["correct"]:
                topic_data[topic]["review_correct"] += 1

        # Calculate percentages
        for topic, data in topic_data.items():
            data["original_score"] = (
                (data["original_correct"] / data["original_total"] * 100)
                if data["original_total"] > 0 else 0
            )
            data["review_score"] = (
                (data["review_correct"] / data["review_total"] * 100)
                if data["review_total"] > 0 else 0
            )
            data["improvement"] = data["review_score"] - data["original_score"]

        return topic_data
