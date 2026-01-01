"""
Quiz selector for final review quiz.
Selects 30 questions from user's previous attempts based on performance.
"""
import logging
import random
from typing import List, Dict, Tuple, Any
from sqlalchemy.orm import Session

from app.models.course import Quiz
from app.models.quiz_attempt import QuizSession, QuizAttempt

logger = logging.getLogger(__name__)


class QuizSelector:
    """
    Selects questions for final review quiz based on user's performance.
    Returns actual quiz data to be used as templates for LLM generation.
    Strategies: balanced, weak_focus, comprehensive
    """

    def __init__(self, db: Session):
        self.db = db

    def select_questions_for_generation(
        self,
        user_id: int,
        course_id: int,
        strategy: str = "balanced",
        question_count: int = 30
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Select existing quiz questions to use as basis for LLM generation.

        Args:
            user_id: User ID
            course_id: Course ID
            strategy: Selection strategy (balanced, weak_focus, comprehensive)
            question_count: Number of questions to select (default: 30)

        Returns:
            Tuple of (selected_quiz_data, distribution_stats)
        """
        try:
            # Get all user's quiz attempts for this course
            attempts = self.db.query(QuizAttempt).join(
                QuizSession, QuizSession.id == QuizAttempt.session_id
            ).filter(
                QuizSession.user_id == user_id,
                QuizSession.course_id == course_id,
                QuizSession.session_type.in_(["regular", "section"])
            ).all()

            if not attempts:
                raise ValueError("No quiz attempts found for this user/course")

            # Calculate performance per quiz
            quiz_performance = {}
            for attempt in attempts:
                quiz_id = int(attempt.quiz_id)  # type: ignore
                if quiz_id not in quiz_performance:
                    quiz_performance[quiz_id] = {
                        "attempts": 0,
                        "correct": 0,
                        "quiz_obj": attempt.quiz
                    }
                quiz_performance[quiz_id]["attempts"] += 1
                if attempt.is_correct:  # type: ignore
                    quiz_performance[quiz_id]["correct"] += 1

            # Calculate accuracy
            for quiz_id, data in quiz_performance.items():
                data["accuracy"] = (data["correct"] / data["attempts"]) * 100

            # Categorize by performance
            weak_quizzes = []
            medium_quizzes = []
            strong_quizzes = []

            for quiz_id, data in quiz_performance.items():
                accuracy = data["accuracy"]
                if accuracy < 60:
                    weak_quizzes.append(quiz_id)
                elif accuracy <= 80:
                    medium_quizzes.append(quiz_id)
                else:
                    strong_quizzes.append(quiz_id)

            logger.info(
                f"Categorized: {len(weak_quizzes)} weak, "
                f"{len(medium_quizzes)} medium, {len(strong_quizzes)} strong"
            )

            # Select based on strategy
            selected_ids = []
            
            if strategy == "weak_focus":
                weak_count = min(int(question_count * 0.7), len(weak_quizzes))
                other_count = question_count - weak_count
                
                if weak_quizzes:
                    selected_ids.extend(random.sample(weak_quizzes, min(weak_count, len(weak_quizzes))))
                
                remaining = medium_quizzes + strong_quizzes
                if remaining and other_count > 0:
                    selected_ids.extend(random.sample(remaining, min(other_count, len(remaining))))

            elif strategy == "comprehensive":
                all_quizzes = weak_quizzes + medium_quizzes + strong_quizzes
                selected_ids = random.sample(all_quizzes, min(question_count, len(all_quizzes)))

            else:  # balanced
                weak_count = int(question_count * 0.4)
                medium_count = int(question_count * 0.4)
                strong_count = question_count - weak_count - medium_count
                
                if weak_quizzes:
                    selected_ids.extend(random.sample(weak_quizzes, min(weak_count, len(weak_quizzes))))
                if medium_quizzes:
                    selected_ids.extend(random.sample(medium_quizzes, min(medium_count, len(medium_quizzes))))
                if strong_quizzes:
                    selected_ids.extend(random.sample(strong_quizzes, min(strong_count, len(strong_quizzes))))
                
                # Fill if needed
                if len(selected_ids) < question_count:
                    all_available = list(set(weak_quizzes + medium_quizzes + strong_quizzes) - set(selected_ids))
                    if all_available:
                        selected_ids.extend(random.sample(all_available, min(question_count - len(selected_ids), len(all_available))))

            # Calculate final distribution
            distribution = {
                "weak_topics": len([qid for qid in selected_ids if qid in weak_quizzes]),
                "medium_topics": len([qid for qid in selected_ids if qid in medium_quizzes]),
                "strong_topics": len([qid for qid in selected_ids if qid in strong_quizzes])
            }

            # Get full quiz data
            selected_quizzes = self.db.query(Quiz).filter(Quiz.id.in_(selected_ids)).all()
            
            quiz_data = [
                {
                    "question": quiz.question,
                    "question_type": quiz.question_type,
                    "question_data": quiz.question_data,
                    "difficulty": quiz.difficulty,
                    "explanation": quiz.explanation
                }
                for quiz in selected_quizzes
            ]

            random.shuffle(quiz_data)

            logger.info(f"Selected {len(quiz_data)} questions: {distribution}")

            return quiz_data, distribution

        except Exception as e:
            logger.error(f"Error selecting questions: {e}")
            raise
