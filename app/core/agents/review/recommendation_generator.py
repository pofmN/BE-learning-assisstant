"""
Recommendation generator using LLM to create personalized study recommendations.
"""
import logging
import json
from typing import List, Dict
from sqlalchemy.orm import Session
from pydantic import BaseModel

from langchain_core.messages import SystemMessage, HumanMessage

from app.core.llm_config import LLMFactory
from app.models.course import Course
from app.core.agents.review.schemas import PerformanceReport, Recommendation, NextSteps
from app.core.agents.review.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    RECOMMENDATION_USER_PROMPT_TEMPLATE,
    GRADE_ASSESSMENT_PROMPT
)

logger = logging.getLogger(__name__)


class RecommendationOutput(BaseModel):
    """Schema for LLM recommendation output."""
    recommendations: List[Dict]
    next_steps: Dict
    motivation_message: str


class GradeOutput(BaseModel):
    """Schema for grade assessment output."""
    grade: str
    assessment: str


class RecommendationGenerator:
    """
    Generates personalized study recommendations using LLM.
    """

    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMFactory.create_llm(temperature=0.7, json_mode=True)
        self.structured_llm = self.llm.with_structured_output(RecommendationOutput)
        self.grade_llm = self.llm.with_structured_output(GradeOutput)

    def generate_recommendations(
        self,
        course_id: int,
        performance_report: PerformanceReport,
        original_score: float,
        review_score: float
    ) -> Dict:
        """
        Generate personalized recommendations based on performance analysis.

        Args:
            course_id: Course ID
            performance_report: Performance analysis report
            original_score: Original average score
            review_score: Review quiz score

        Returns:
            Dict with recommendations and next steps
        """
        try:
            # Get course info
            course = self.db.query(Course).filter(Course.id == course_id).first()
            course_title = str(course.title) if course else "Course"  # type: ignore

            # Format topic breakdown for prompt
            topic_breakdown = self._format_topic_breakdown(performance_report.topic_analysis)
            weak_topics_list = self._format_topic_list(performance_report.weak_topics, "weak")
            strong_topics_list = self._format_topic_list(performance_report.strong_topics, "strong")

            improvement = review_score - original_score

            # Build prompt
            user_prompt = RECOMMENDATION_USER_PROMPT_TEMPLATE.format(
                course_title=course_title,
                original_score=original_score,
                review_score=review_score,
                improvement=improvement,
                improved_count=len(performance_report.improved_questions),
                regressed_count=len(performance_report.regressed_questions),
                persistent_weak_count=len(performance_report.persistent_weaknesses),
                consistent_strong_count=len(performance_report.consistent_strengths),
                topic_breakdown=topic_breakdown,
                weak_topics_list=weak_topics_list,
                strong_topics_list=strong_topics_list
            )

            # Call LLM for recommendations
            messages = [
                SystemMessage(content=RECOMMENDATION_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]

            result = self.structured_llm.invoke(messages)

            # Get grade assessment
            grade_result = self._get_grade_assessment(review_score)

            # Format recommendations
            recommendations = []
            for rec in result.recommendations:  # type: ignore
                recommendations.append(Recommendation(
                    priority=rec.get("priority", "medium"),
                    topic=rec.get("topic", ""),
                    suggestion=rec.get("suggestion", ""),
                    reason=rec.get("reason", ""),
                    study_resources=rec.get("study_resources", [])
                ))

            # Format next steps
            next_steps_data = result.next_steps  # type: ignore
            next_steps = NextSteps(
                weak_topics=next_steps_data.get("weak_topics", []),
                suggested_study_time=next_steps_data.get("suggested_study_time", "2-3 hours"),
                review_again_after=next_steps_data.get("review_again_after", "7 days"),
                confidence_level=next_steps_data.get("confidence_level", "medium")
            )

            logger.info(f"Generated {len(recommendations)} recommendations for course {course_id}")

            return {
                "recommendations": [rec.dict() for rec in recommendations],
                "next_steps": next_steps.model_dump(),
                "grade": grade_result["grade"],
                "motivation_message": result.motivation_message  # type: ignore
            }

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            # Return fallback recommendations
            return self._generate_fallback_recommendations(performance_report, review_score)

    def _format_topic_breakdown(self, topic_analysis: Dict[str, Dict]) -> str:
        """Format topic analysis for prompt."""
        if not topic_analysis:
            return "No topic-specific data available."

        lines = []
        for topic, data in topic_analysis.items():
            orig = data.get("original_score", 0)
            review = data.get("review_score", 0)
            improvement = data.get("improvement", 0)
            lines.append(
                f"- {topic}: Original {orig:.1f}% → Review {review:.1f}% ({improvement:+.1f}%)"
            )
        return "\n".join(lines)

    def _format_topic_list(self, topics: List[str], category: str) -> str:
        """Format topic list for prompt."""
        if not topics:
            return f"No {category} topics identified."
        return "\n".join([f"- {topic}" for topic in topics])

    def _get_grade_assessment(self, score: float) -> Dict:
        """Get grade and assessment for score."""
        try:
            prompt = GRADE_ASSESSMENT_PROMPT.format(score=score)
            messages = [HumanMessage(content=prompt)]
            result = self.grade_llm.invoke(messages)
            return {
                "grade": result.grade,  # type: ignore
                "assessment": result.assessment  # type: ignore
            }
        except Exception as e:
            logger.error(f"Error getting grade assessment: {e}")
            # Fallback grading
            if score >= 90:
                return {"grade": "A", "assessment": "Excellent understanding"}
            elif score >= 80:
                return {"grade": "B", "assessment": "Good understanding"}
            elif score >= 70:
                return {"grade": "C", "assessment": "Satisfactory understanding"}
            elif score >= 60:
                return {"grade": "D", "assessment": "Needs improvement"}
            else:
                return {"grade": "F", "assessment": "Significant gaps in knowledge"}

    def _generate_fallback_recommendations(
        self,
        performance_report: PerformanceReport,
        review_score: float
    ) -> Dict:
        """Generate fallback recommendations if LLM fails."""
        recommendations = []

        # Recommend focusing on persistent weaknesses
        if performance_report.persistent_weaknesses:
            recommendations.append({
                "priority": "high",
                "topic": "Persistent Weak Areas",
                "suggestion": "Focus on questions you got wrong both times. Review the explanations carefully and try similar practice problems.",
                "reason": f"You have {len(performance_report.persistent_weaknesses)} questions that remain challenging.",
                "study_resources": []
            })

        # Recommend reviewing regressed topics
        if performance_report.regressed_questions:
            recommendations.append({
                "priority": "medium",
                "topic": "Topics Needing Review",
                "suggestion": "Review topics where you regressed. These concepts may need reinforcement.",
                "reason": f"{len(performance_report.regressed_questions)} questions went from correct to incorrect.",
                "study_resources": []
            })

        return {
            "recommendations": recommendations,
            "next_steps": {
                "weak_topics": performance_report.weak_topics,
                "suggested_study_time": "3-4 hours",
                "review_again_after": "7 days",
                "confidence_level": "medium" if review_score >= 70 else "low"
            },
            "grade": self._get_grade_assessment(review_score)["grade"],
            "motivation_message": "Keep practicing and reviewing difficult concepts. You're making progress!"
        }
