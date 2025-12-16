# Frontend Integration Guide - AI Learning Assistant Backend

## Overview

This document explains all backend endpoints for building the frontend. The system allows users to:

1. Upload documents → Generate courses with quizzes, flashcards, and study notes
2. Take quizzes with immediate feedback and grading
3. Study flashcards with spaced repetition
4. Track learning progress and statistics

---

## Complete User Flow

### 1. Document Upload & Course Generation

**Step 1: Upload Document**

```
POST /api/v1/documents/upload
Content-Type: multipart/form-data

Request:
- file: PDF/DOCX file

Response:
{
  "id": 123,
  "filename": "biology_notes.pdf",
  "status": "processing",
  "message": "Document uploaded and processing started"
}
```

**Step 2: Create Course from Document**

```
POST /api/v1/courses/create
Content-Type: application/json

Request:
{
  "document_id": 123,
  "language": "English",
  "level": "Intermediate",
  "question_type": ["multiple_choice", "true_false"],
  "requirements": "Focus on key concepts"
}

Response (202 Accepted):
{
  "course_id": 456,
  "status": "processing",
  "message": "Course generation started. Poll GET /courses/{course_id}/status to check status."
}
```

**Step 3: Poll Course Status**

```
GET /api/v1/courses/456/status

Response:
{
  "id": 456,
  "document_id": 123,
  "title": "Biology Fundamentals",
  "description": "Comprehensive biology course covering...",
  "status": "completed",  // or "processing", "failed"
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

---

### 2. Taking Quizzes

**Step 1: Start Quiz Session**

```
POST /api/v1/quiz/sessions/start

Request:
{
  "course_id": 456,
  "section_id": 10  // Optional: null for all sections
}

Response (201 Created):
{
  "session_id": 789,
  "course_id": 456,
  "section_id": 10,
  "total_questions": 15,
  "status": "in_progress",
  "started_at": "2024-01-15T11:00:00Z"
}
```

**Step 2: Get Quiz Questions**

```
GET /api/v1/quiz/sessions/789/questions

Response:
[
  {
    "quiz_id": 1,
    "question": "What is photosynthesis?",
    "question_type": "multiple_choice",
    "question_data": {
      "options": [
        {"id": "a", "text": "Energy production"},
        {"id": "b", "text": "Light conversion to energy"},
        {"id": "c", "text": "Cell division"},
        {"id": "d", "text": "Respiration"}
      ]
    },
    "difficulty": "easy"
  },
  {
    "quiz_id": 2,
    "question": "Plants need sunlight to grow.",
    "question_type": "true_false",
    "question_data": {},
    "difficulty": "easy"
  }
]
```

**Step 3: Submit Answer (for each question)**

```
POST /api/v1/quiz/sessions/789/submit

Request:
{
  "quiz_id": 1,
  "user_answer": {
    "selected_id": "b"  // For multiple choice
  },
  "time_spent": 15  // seconds
}

Response:
{
  "attempt_id": 101,
  "quiz_id": 1,
  "is_correct": true,
  "user_answer": {"selected_id": "b"},
  "correct_answer": {
    "correct_answer_id": "b",
    "options": [...]
  },
  "explanation": "Photosynthesis is the process where plants convert light energy...",
  "question": "What is photosynthesis?",
  "question_type": "multiple_choice"
}
```

**Answer Formats by Question Type:**

```javascript
// Multiple Choice
{
  "quiz_id": 1,
  "user_answer": {
    "selected_id": "b"
  }
}

// True/False
{
  "quiz_id": 2,
  "user_answer": {
    "answer": true
  }
}

// Matching
{
  "quiz_id": 3,
  "user_answer": {
    "matches": {
      "left_1": "right_2",
      "left_2": "right_1"
    }
  }
}

// Short Answer
{
  "quiz_id": 4,
  "user_answer": {
    "answer": "Mitochondria"
  }
}
```

**Step 4: Complete Quiz Session**

```
POST /api/v1/quiz/sessions/789/complete

Response:
{
  "session_id": 789,
  "total_questions": 15,
  "correct_answers": 12,
  "incorrect_answers": 3,
  "score_percentage": 80.0,
  "completed_at": "2024-01-15T11:15:00Z",
  "attempts": [
    {
      "attempt_id": 101,
      "quiz_id": 1,
      "is_correct": true,
      "user_answer": {...},
      "correct_answer": {...},
      "explanation": "...",
      "question": "What is photosynthesis?",
      "question_type": "multiple_choice"
    },
    // ... more attempts
  ]
}
```

**Step 5: Review Past Quiz Results**

```
GET /api/v1/quiz/sessions/789/results

Response: (same as complete response)
```

**Get Quiz History**

```
GET /api/v1/quiz/history?course_id=456&limit=10

Response:
[
  {
    "session_id": 789,
    "course_id": 456,
    "section_id": 10,
    "total_questions": 15,
    "status": "completed",
    "started_at": "2024-01-15T11:00:00Z"
  },
  // ... more sessions
]
```

---

### 3. Flashcard Study

**Step 1: Get Flashcards for Course**

```
GET /api/v1/flashcards/courses/456/flashcards?section_id=10&due_only=false

Response:
[
  {
    "id": 201,
    "course_id": 456,
    "section_id": 10,
    "question": "What is ATP?",
    "answer": "Adenosine triphosphate - the energy currency of cells",
    "times_reviewed": 3,
    "avg_confidence": 4.0,
    "next_review": "2024-01-16T10:00:00Z"
  },
  // ... more flashcards
]
```

**Step 2: Review Flashcard**

```
POST /api/v1/flashcards/review

Request:
{
  "flashcard_id": 201,
  "confidence_level": 4,  // 1-5 scale
  "time_spent": 20  // seconds
}

Response (201 Created):
{
  "review_id": 301,
  "flashcard_id": 201,
  "confidence_level": 4,
  "next_review_date": "2024-01-22T10:00:00Z",  // 1 week later
  "message": "Flashcard reviewed successfully"
}
```

**Confidence Levels (Spaced Repetition):**

- **1**: Review in 1 hour (didn't know it)
- **2**: Review in 1 day (struggled)
- **3**: Review in 3 days (okay)
- **4**: Review in 1 week (good)
- **5**: Review in 2 weeks (mastered)

**Step 3: Get Flashcard Stats**

```
GET /api/v1/flashcards/courses/456/flashcards/stats

Response:
{
  "course_id": 456,
  "cards_reviewed": 45,
  "avg_confidence": 3.8,
  "total_time_seconds": 1800,
  "cards_to_review": 12  // Due now
}
```

---

### 4. Progress Tracking

**Course Progress**

```
GET /api/v1/progress/courses/456/progress

Response:
{
  "course_id": 456,
  "course_title": "Biology Fundamentals",
  "total_sections": 8,
  "quiz_sessions_completed": 5,
  "avg_quiz_score": 82.5,
  "flashcards_total": 60,
  "flashcards_reviewed": 45,
  "last_activity": "2024-01-15T11:15:00Z",
  "completion_percentage": 75.0
}
```

**Section Progress**

```
GET /api/v1/progress/courses/456/sections/progress

Response:
[
  {
    "section_id": 10,
    "section_title": "Cell Structure",
    "quizzes_total": 5,
    "quizzes_attempted": 5,
    "quiz_avg_score": 85.0,
    "flashcards_total": 10,
    "flashcards_reviewed": 8,
    "is_completed": false
  },
  // ... more sections
]
```

**Overall Statistics**

```
GET /api/v1/progress/stats/overview

Response:
{
  "total_courses": 3,
  "courses_in_progress": 2,
  "total_quiz_sessions": 15,
  "total_quizzes_attempted": 120,
  "avg_quiz_score": 78.5,
  "total_flashcards_reviewed": 250,
  "total_study_time_minutes": 450,
  "current_streak_days": 7
}
```

---

## Frontend Implementation Examples

### React Example: Quiz Component

```jsx
import React, { useState, useEffect } from "react";
import axios from "axios";

function QuizSession({ courseId, sectionId }) {
  const [session, setSession] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [results, setResults] = useState(null);

  // Start quiz session
  useEffect(() => {
    const startQuiz = async () => {
      const response = await axios.post("/api/v1/quiz/sessions/start", {
        course_id: courseId,
        section_id: sectionId,
      });
      setSession(response.data);

      // Get questions
      const questionsResponse = await axios.get(
        `/api/v1/quiz/sessions/${response.data.session_id}/questions`
      );
      setQuestions(questionsResponse.data);
    };

    startQuiz();
  }, [courseId, sectionId]);

  // Submit answer
  const handleSubmit = async () => {
    const response = await axios.post(
      `/api/v1/quiz/sessions/${session.session_id}/submit`,
      {
        quiz_id: questions[currentQuestion].quiz_id,
        user_answer: selectedAnswer,
        time_spent: 30,
      }
    );

    setFeedback(response.data);
  };

  // Next question
  const handleNext = () => {
    setFeedback(null);
    setSelectedAnswer(null);

    if (currentQuestion + 1 < questions.length) {
      setCurrentQuestion(currentQuestion + 1);
    } else {
      completeQuiz();
    }
  };

  // Complete quiz
  const completeQuiz = async () => {
    const response = await axios.post(
      `/api/v1/quiz/sessions/${session.session_id}/complete`
    );
    setResults(response.data);
  };

  if (results) {
    return (
      <div className="quiz-results">
        <h2>Quiz Complete!</h2>
        <p>Score: {results.score_percentage}%</p>
        <p>
          Correct: {results.correct_answers} / {results.total_questions}
        </p>

        <h3>Review:</h3>
        {results.attempts.map((attempt, idx) => (
          <div
            key={idx}
            className={attempt.is_correct ? "correct" : "incorrect"}
          >
            <p>
              <strong>{attempt.question}</strong>
            </p>
            <p>{attempt.is_correct ? "✓ Correct" : "✗ Incorrect"}</p>
            <p>
              <em>{attempt.explanation}</em>
            </p>
          </div>
        ))}
      </div>
    );
  }

  if (!questions.length) return <div>Loading...</div>;

  const question = questions[currentQuestion];

  return (
    <div className="quiz-session">
      <h2>
        Question {currentQuestion + 1} of {questions.length}
      </h2>

      <div className="question">
        <p>{question.question}</p>

        {question.question_type === "multiple_choice" && (
          <div>
            {question.question_data.options.map((option) => (
              <label key={option.id}>
                <input
                  type="radio"
                  name="answer"
                  value={option.id}
                  onChange={() => setSelectedAnswer({ selected_id: option.id })}
                  disabled={feedback !== null}
                />
                {option.text}
              </label>
            ))}
          </div>
        )}

        {question.question_type === "true_false" && (
          <div>
            <button onClick={() => setSelectedAnswer({ answer: true })}>
              True
            </button>
            <button onClick={() => setSelectedAnswer({ answer: false })}>
              False
            </button>
          </div>
        )}
      </div>

      {!feedback && (
        <button onClick={handleSubmit} disabled={!selectedAnswer}>
          Submit Answer
        </button>
      )}

      {feedback && (
        <div
          className={`feedback ${
            feedback.is_correct ? "correct" : "incorrect"
          }`}
        >
          <p>{feedback.is_correct ? "✓ Correct!" : "✗ Incorrect"}</p>
          <p>{feedback.explanation}</p>
          <button onClick={handleNext}>Next Question</button>
        </div>
      )}
    </div>
  );
}
```

### Vue Example: Flashcard Component

```vue
<template>
  <div class="flashcard-study">
    <div v-if="!currentCard" class="loading">
      <button @click="loadFlashcards">Start Studying</button>
    </div>

    <div v-else class="card" :class="{ flipped: isFlipped }">
      <div class="card-front" @click="flipCard">
        <h3>Question:</h3>
        <p>{{ currentCard.question }}</p>
        <small>Click to reveal answer</small>
      </div>

      <div class="card-back">
        <h3>Answer:</h3>
        <p>{{ currentCard.answer }}</p>

        <div class="confidence-buttons">
          <button @click="reviewCard(1)">😞 1</button>
          <button @click="reviewCard(2)">😐 2</button>
          <button @click="reviewCard(3)">🙂 3</button>
          <button @click="reviewCard(4)">😊 4</button>
          <button @click="reviewCard(5)">🤩 5</button>
        </div>
      </div>
    </div>

    <div class="progress">
      Card {{ currentIndex + 1 }} of {{ flashcards.length }}
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      flashcards: [],
      currentIndex: 0,
      isFlipped: false,
    };
  },
  computed: {
    currentCard() {
      return this.flashcards[this.currentIndex] || null;
    },
  },
  methods: {
    async loadFlashcards() {
      const response = await this.$axios.get(
        `/api/v1/flashcards/courses/${this.courseId}/flashcards`,
        { params: { due_only: true } }
      );
      this.flashcards = response.data;
    },

    flipCard() {
      this.isFlipped = !this.isFlipped;
    },

    async reviewCard(confidence) {
      await this.$axios.post("/api/v1/flashcards/review", {
        flashcard_id: this.currentCard.id,
        confidence_level: confidence,
        time_spent: 30,
      });

      this.isFlipped = false;

      if (this.currentIndex + 1 < this.flashcards.length) {
        this.currentIndex++;
      } else {
        alert("All done! Great work!");
      }
    },
  },
};
</script>
```

---

## Database Schema Summary

**Users**

- id, email, username, password_hash

**Documents**

- id, owner_id, filename, status

**Courses**

- id, document_id, title, description, language, level, status

**CourseSections**

- id, course_id, title, content, section_order, cluster_id

**Quizzes**

- id, course_id, section_id, question, question_type, question_data, explanation, difficulty

**FlashCards**

- id, course_id, section_id, question, answer

**StudiesNotes**

- id, course_id, section_id, title, content

**QuizSessions**

- id, user_id, course_id, section_id, status, total_questions, correct_answers, score_percentage

**QuizAttempts**

- id, session_id, quiz_id, user_id, user_answer, is_correct, time_spent

**FlashcardReviews**

- id, flashcard_id, user_id, confidence_level, next_review_date

---

## Error Handling

All endpoints return standard HTTP status codes:

**Success:**

- 200 OK - Successful GET
- 201 Created - Resource created
- 202 Accepted - Async task started

**Client Errors:**

- 400 Bad Request - Invalid input
- 401 Unauthorized - Not logged in
- 403 Forbidden - No access
- 404 Not Found - Resource doesn't exist

**Server Errors:**

- 500 Internal Server Error

Example error response:

```json
{
  "detail": "Course not found"
}
```

---

## Authentication

All endpoints (except auth) require JWT token:

```javascript
axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
```

---

## Tips for Frontend Development

1. **Poll course status** every 5 seconds until status = "completed"
2. **Show loading states** during async operations
3. **Cache flashcards** to avoid re-fetching
4. **Track time spent** for better analytics
5. **Show progress bars** for motivation
6. **Implement keyboard shortcuts** (next question, flip card)
7. **Add animations** for card flips and answer feedback
8. **Use optimistic updates** for better UX

---

## Next Steps

1. Add study notes viewing endpoints
2. Implement leaderboards
3. Add social features (share results)
4. Export progress reports
5. Add gamification (badges, achievements)
