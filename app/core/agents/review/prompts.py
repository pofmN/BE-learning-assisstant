"""
Prompts for review quiz recommendation generation.
"""

# System prompt for recommendation generation
RECOMMENDATION_SYSTEM_PROMPT = """You are an expert educational advisor helping students improve their learning outcomes.

Your task is to analyze a student's performance on a final review quiz and generate personalized, actionable study recommendations.

Guidelines:
- Be specific and practical
- Focus on weak areas but also acknowledge strengths
- Provide concrete study strategies
- Be encouraging and motivating
- Prioritize recommendations by impact
- Suggest specific resources when applicable"""


# User prompt template for generating recommendations
RECOMMENDATION_USER_PROMPT_TEMPLATE = """Course: {course_title}

## Performance Summary
- Original Average Score: {original_score:.1f}%
- Review Quiz Score: {review_score:.1f}%
- Improvement: {improvement:+.1f}%

## Question-Level Breakdown
- Improved (was wrong, now correct): {improved_count}
- Regressed (was correct, now wrong): {regressed_count}
- Persistent Weaknesses (still wrong): {persistent_weak_count}
- Consistent Strengths (still correct): {consistent_strong_count}

## Topic Analysis
{topic_breakdown}

## Weak Topics Requiring Focus
{weak_topics_list}

## Strong Topics (Maintaining Well)
{strong_topics_list}

Based on this performance data, generate 3-5 prioritized study recommendations in JSON format:

```json
{{
  "recommendations": [
    {{
      "priority": "high|medium|low",
      "topic": "Topic name",
      "suggestion": "Specific, actionable study suggestion (2-3 sentences)",
      "reason": "Why this is important based on performance data (1-2 sentences)",
      "study_resources": ["Resource 1", "Resource 2"]
    }}
  ],
  "next_steps": {{
    "weak_topics": ["Topic 1", "Topic 2"],
    "suggested_study_time": "X-Y hours",
    "review_again_after": "X days",
    "confidence_level": "low|medium|high"
  }},
  "motivation_message": "Encouraging message about progress and next steps (2-3 sentences)"
}}
```

Focus recommendations on:
1. Persistent weaknesses (highest priority)
2. Topics with regression
3. Topics with low scores
4. Reinforcement strategies for improving topics
5. Maintenance for strong topics"""


# Prompt template for generating grade assessment
GRADE_ASSESSMENT_PROMPT = """Based on a review quiz score of {score:.1f}%, assign a letter grade (A, B, C, D, F) and brief assessment:

Grading scale:
- A (90-100): Excellent understanding
- B (80-89): Good understanding
- C (70-79): Satisfactory understanding
- D (60-69): Needs improvement
- F (0-59): Significant gaps

Return JSON:
{{
  "grade": "A|B|C|D|F",
  "assessment": "One sentence assessment"
}}"""


# ============= Quiz Generation Prompts =============

# ============= Quiz Generation Prompts =============

QUIZ_GENERATION_SYSTEM_PROMPT = """You are an expert quiz creator. Generate new quiz questions based on the provided examples.

Output must be a valid JSON object with a 'questions' key containing a list of quiz objects.

Each quiz object MUST have the following structure:

For Multiple Choice questions:
{{
  "question": "The question text",
  "question_type": "multiple_choice",
  "question_data": {{
    "options": [{{"id": "A", "text": "Option A"}}, {{"id": "B", "text": "Option B"}}, ...],
    "correct_answer_id": "A",
    "shuffle": true
  }},
  "explanation": "Explanation of why the answer is correct",
  "difficulty": "easy" | "medium" | "hard"
}}

For True/False questions:
{{
  "question": "The question text",
  "question_type": "true_false",
  "question_data": {{
    "statement": "The statement to evaluate",
    "correct_answer": true | false
  }},
  "explanation": "Explanation of the answer",
  "difficulty": "easy" | "medium" | "hard"
}}

For Matching questions:
{{
  "question": "The question text",
  "question_type": "matching",
  "question_data": {{
    "left_side": [{{"id": "L1", "text": "Term 1"}}, {{"id": "L2", "text": "Term 2"}}],
    "right_side": [{{"id": "R1", "text": "Definition 1"}}, {{"id": "R2", "text": "Definition 2"}}],
    "correct_matches": {{"L1": "R1", "L2": "R2"}},
    "shuffle_right_side": true
  }},
  "explanation": "Explanation of the matches",
  "difficulty": "easy" | "medium" | "hard"
}}

Requirements:
- Match the question types from examples
- Keep similar difficulty levels
- Create UNIQUE questions (not copies of examples)
- Include correct answers and explanations

IMPORTANT: Return ONLY the raw JSON object. DO NOT wrap it in markdown code blocks or any other text. **JUST RETURN THE JSON.**"""


QUIZ_GENERATION_USER_PROMPT = """Create EXACTLY {count} NEW quiz questions based on these examples:

{examples}

Generate exactly {count} questions matching the formats above.

Return ONLY a JSON object with a 'questions' key containing the array of quiz objects."""
