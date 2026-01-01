"""
Quiz generator for final review quiz.
Uses LLM to generate new quiz questions based on existing quiz examples.
"""
import logging
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.llm_config import LLMFactory
from app.core.agents.review.prompts import (
    QUIZ_GENERATION_SYSTEM_PROMPT,
    QUIZ_GENERATION_USER_PROMPT
)

logger = logging.getLogger(__name__)


class QuizGenerator:
    """
    Generates new quiz questions using LLM based on existing quiz examples.
    """

    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMFactory.create_llm(
            model="gpt-4o-mini",
            temperature=0.8,
            json_mode=False,
            tracing_project="review-quiz-generation"
        )

    def generate_questions(
        self,
        example_quizzes: List[Dict[str, Any]],
        question_count: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Generate new quiz questions based on examples.

        Args:
            example_quizzes: List of existing quiz data to use as templates
            question_count: Number of questions to generate

        Returns:
            List of generated quiz questions
        """
        try:
            # Format examples for prompt
            examples_text = self._format_examples(example_quizzes)

            # Build prompt
            user_prompt = QUIZ_GENERATION_USER_PROMPT.format(
                count=question_count,
                examples=examples_text
            )

            logger.info(f"Generating {question_count} questions with LLM...")

            # Call LLM
            messages = [
                {"role": "system", "content": QUIZ_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]

            response = self.llm.invoke(messages)
            response_text = str(response.content)

            # Parse response
            questions = self._parse_response(response_text, question_count)

            logger.info(f"Successfully generated {len(questions)} questions")

            return questions

        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            # Return fallback
            return self._create_fallback_questions(example_quizzes, question_count)

    def _format_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Format quiz examples for prompt."""
        formatted = []
        for i, ex in enumerate(examples[:10], 1):  # Limit to 10 examples to save tokens
            formatted.append(
                f"{i}. Question: {ex.get('question', 'N/A')}\n"
                f"   Type: {ex.get('question_type', 'N/A')}\n"
                f"   Difficulty: {ex.get('difficulty', 'medium')}"
            )
        return "\n\n".join(formatted)

    def _parse_response(self, response_text: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse LLM response."""
        try:
            # Extract JSON
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            questions = json.loads(response_text)

            if not isinstance(questions, list):
                raise ValueError("Response is not a list")

            # Validate
            validated = [q for q in questions if self._validate_question(q)]

            if len(validated) < expected_count * 0.5:
                raise ValueError(f"Only {len(validated)}/{expected_count} valid questions")

            return validated[:expected_count]

        except Exception as e:
            logger.error(f"Parse error: {e}")
            raise

    def _validate_question(self, q: Dict[str, Any]) -> bool:
        """Validate question structure."""
        if not all(k in q for k in ["question", "question_type", "question_data"]):
            return False

        q_type = q.get("question_type")
        q_data = q.get("question_data", {})

        if q_type == "multiple_choice":
            return "options" in q_data and "correct_answer" in q_data
        elif q_type == "true_false":
            return "correct_answer" in q_data
        elif q_type == "matching":
            return all(k in q_data for k in ["terms", "definitions", "correct_matches"])
        elif q_type == "short_answer":
            return "correct_answer" in q_data

        return False

    def _create_fallback_questions(
        self,
        examples: List[Dict[str, Any]],
        count: int
    ) -> List[Dict[str, Any]]:
        """Create fallback questions if LLM fails."""
        logger.warning("Using fallback question generation")
        
        fallback = []
        for i in range(min(count, len(examples))):
            ex = examples[i % len(examples)]
            fallback.append({
                "question": f"Review question {i+1}: {ex.get('question', 'Question')}",
                "question_type": ex.get("question_type", "multiple_choice"),
                "question_data": ex.get("question_data", {}),
                "difficulty": ex.get("difficulty", "medium"),
                "explanation": ex.get("explanation", "Review this concept.")
            })
        
        return fallback[:count]
