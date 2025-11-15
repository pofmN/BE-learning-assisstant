# API Testing Examples

This document provides examples of how to test the API endpoints using curl or HTTPie.

## Authentication

### Register a new user

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@example.com",
    "username": "student1",
    "full_name": "John Doe",
    "password": "password123"
  }'
```

### Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=student@example.com&password=password123"
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Get current user

```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Document Management

### Upload a document

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "title=Machine Learning Basics" \
  -F "file=@/path/to/document.pdf"
```

### List documents

```bash
curl -X GET "http://localhost:8000/api/v1/documents" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Get document details

```bash
curl -X GET "http://localhost:8000/api/v1/documents/1" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Delete document

```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/1" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## MCQ Generation

### Generate MCQs from document

```bash
curl -X POST "http://localhost:8000/api/v1/mcqs/generate" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": 1,
    "num_questions": 10,
    "difficulty": "medium",
    "topic": "Machine Learning"
  }'
```

### List MCQs

```bash
curl -X GET "http://localhost:8000/api/v1/mcqs?document_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Get MCQ details

```bash
curl -X GET "http://localhost:8000/api/v1/mcqs/1" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Knowledge Testing

### Submit test answers

```bash
curl -X POST "http://localhost:8000/api/v1/tests/submit" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Machine Learning Quiz 1",
    "answers": [
      {"mcq_id": 1, "user_answer": "A"},
      {"mcq_id": 2, "user_answer": "B"},
      {"mcq_id": 3, "user_answer": "C"}
    ]
  }'
```

### Get test results

```bash
curl -X GET "http://localhost:8000/api/v1/tests/results" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Get specific test result

```bash
curl -X GET "http://localhost:8000/api/v1/tests/results/1" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Personalized Learning

### Get learning progress

```bash
curl -X GET "http://localhost:8000/api/v1/learning/progress" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Get recommendations

```bash
curl -X GET "http://localhost:8000/api/v1/learning/recommendations" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Get weak areas

```bash
curl -X GET "http://localhost:8000/api/v1/learning/weak-areas" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Virtual Teacher WebSocket

Connect to the WebSocket endpoint for interactive chat:

```javascript
const ws = new WebSocket(
  "ws://localhost:8000/api/v1/chat/ws?token=YOUR_TOKEN_HERE&document_id=1"
);

ws.onopen = () => {
  console.log("Connected to virtual teacher");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.type}: ${data.message}`);
};

// Send a message
ws.send(
  JSON.stringify({
    message: "Can you explain machine learning?",
  })
);
```

## Health Check

```bash
curl -X GET "http://localhost:8000/health"
```

## API Documentation

Visit the interactive API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
