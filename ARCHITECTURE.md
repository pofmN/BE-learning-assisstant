# System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Applications                          │
│                   (Web, Mobile, Desktop)                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTPS/WSS
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                        FastAPI Backend                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   API Layer (v1)                             │  │
│  │  ┌─────────┬─────────┬─────────┬─────────┬─────────────┐   │  │
│  │  │  Auth   │Documents│  MCQs   │  Tests  │  Learning   │   │  │
│  │  └─────────┴─────────┴─────────┴─────────┴─────────────┘   │  │
│  │  ┌───────────────────────────────────────────────────────┐  │  │
│  │  │            WebSocket (Virtual Teacher)                │  │  │
│  │  └───────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Business Logic Layer                       │  │
│  │  ┌────────────────┬────────────────┬────────────────────┐   │  │
│  │  │  AI Service    │  Document      │  Learning          │   │  │
│  │  │  (MCQ Gen)     │  Parser        │  Analytics         │   │  │
│  │  └────────────────┴────────────────┴────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Data Access Layer                          │  │
│  │                    (SQLAlchemy ORM)                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
    ┌───────────▼──────────┐  ┌──────────▼─────────────┐
    │   PostgreSQL DB      │  │   File Storage         │
    │   (User, Document,   │  │   (Uploads)            │
    │   MCQ, Test, etc.)   │  │   PDF/DOCX/PPTX        │
    └──────────────────────┘  └────────────────────────┘
                                          │
                             ┌────────────▼────────────┐
                             │   AI Model Server       │
                             │   (T5/LLM for MCQ Gen)  │
                             └─────────────────────────┘
```

## Database Schema

```
┌─────────────────┐
│     Users       │
├─────────────────┤
│ id (PK)         │
│ email           │
│ username        │
│ hashed_password │
│ role            │
│ is_active       │
└────────┬────────┘
         │
         │ 1:N
         │
┌────────▼────────────┐
│    Documents        │
├─────────────────────┤
│ id (PK)             │
│ title               │
│ file_path           │
│ file_type           │
│ extracted_text      │
│ owner_id (FK)       │
└──────────┬──────────┘
           │
           │ 1:N
           │
┌──────────▼──────────┐
│       MCQs          │
├─────────────────────┤
│ id (PK)             │
│ question            │
│ choices (JSON)      │
│ correct_answer      │
│ explanation         │
│ difficulty          │
│ topic               │
│ document_id (FK)    │
└─────────────────────┘

┌─────────────────────┐
│   TestResults       │
├─────────────────────┤
│ id (PK)             │
│ user_id (FK)        │───┐
│ title               │   │
│ total_questions     │   │
│ correct_answers     │   │
│ score               │   │
└──────────┬──────────┘   │
           │              │
           │ 1:N          │ N:1
           │              │
┌──────────▼──────────┐   │
│   TestAnswers       │   │
├─────────────────────┤   │
│ id (PK)             │   │
│ test_result_id (FK) │   │
│ mcq_id (FK)         │   │
│ user_answer         │   │
│ is_correct          │   │
└─────────────────────┘   │
                          │
┌─────────────────────────┤
│  LearningProgress       │
├─────────────────────────┤
│ id (PK)                 │
│ user_id (FK)            │
│ topic                   │
│ total_attempts          │
│ correct_attempts        │
│ accuracy                │
│ weak_areas (JSON)       │
└─────────────────────────┘
```

## Request Flow

### 1. Document Upload & MCQ Generation

```
Client
  │
  │ POST /api/v1/documents/upload
  │ (with PDF/DOCX/PPTX file)
  │
  ▼
FastAPI Endpoint
  │
  ├─► Validate JWT token
  │
  ├─► Save file to disk
  │
  ├─► Extract text (PyPDF2/python-docx/python-pptx)
  │
  ├─► Save to database
  │
  └─► Return document metadata


Client
  │
  │ POST /api/v1/mcqs/generate
  │ (document_id, num_questions, difficulty)
  │
  ▼
FastAPI Endpoint
  │
  ├─► Validate JWT token
  │
  ├─► Get document from DB
  │
  ├─► Call AI Service
  │     │
  │     ├─► Send text to AI model
  │     │
  │     └─► Parse MCQ response
  │
  ├─► Save MCQs to database
  │
  └─► Return generated MCQs
```

### 2. Knowledge Testing Flow

```
Client
  │
  │ POST /api/v1/tests/submit
  │ (title, answers[{mcq_id, user_answer}])
  │
  ▼
FastAPI Endpoint
  │
  ├─► Validate JWT token
  │
  ├─► Fetch MCQs from DB
  │
  ├─► Evaluate answers
  │     │
  │     ├─► Compare user_answer vs correct_answer
  │     │
  │     └─► Calculate score
  │
  ├─► Save TestResult
  │
  ├─► Save TestAnswers
  │
  ├─► Update LearningProgress
  │
  └─► Return detailed results
```

### 3. Personalized Learning Flow

```
Client
  │
  │ GET /api/v1/learning/recommendations
  │
  ▼
FastAPI Endpoint
  │
  ├─► Validate JWT token
  │
  ├─► Get LearningProgress records
  │
  ├─► Analyze performance
  │     │
  │     ├─► Identify weak topics (accuracy < 60%)
  │     │
  │     ├─► Identify topics needing practice
  │     │
  │     └─► Generate recommendations
  │
  └─► Return personalized recommendations
```

### 4. Virtual Teacher Chat (WebSocket)

```
Client
  │
  │ WS /api/v1/chat/ws?token=JWT_TOKEN
  │
  ▼
WebSocket Connection
  │
  ├─► Validate JWT token
  │
  ├─► Accept connection
  │
  └─► Message loop
        │
        ├─► Receive user message
        │
        ├─► Get context (document, history)
        │
        ├─► Call AI Service
        │
        ├─► Stream response
        │
        └─► Send to client
```

## Authentication Flow

```
┌──────────┐                                ┌──────────────┐
│  Client  │                                │   Backend    │
└─────┬────┘                                └──────┬───────┘
      │                                             │
      │  POST /api/v1/auth/register                │
      │  {email, username, password}               │
      ├────────────────────────────────────────────►
      │                                             │
      │         ◄───────────────────────────────────┤
      │         {user_data}                         │
      │                                             │
      │  POST /api/v1/auth/login                   │
      │  {username, password}                       │
      ├────────────────────────────────────────────►
      │                                             │
      │         Verify password                     │
      │         Generate JWT token                  │
      │                                             │
      │         ◄───────────────────────────────────┤
      │         {access_token, token_type}          │
      │                                             │
      │  GET /api/v1/documents                     │
      │  Authorization: Bearer <token>              │
      ├────────────────────────────────────────────►
      │                                             │
      │         Validate JWT                        │
      │         Get user from token                 │
      │         Query documents                     │
      │                                             │
      │         ◄───────────────────────────────────┤
      │         [documents]                         │
      │                                             │
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer                          │
│                   (Nginx/HAProxy)                           │
└────────────┬────────────────────────────┬───────────────────┘
             │                            │
    ┌────────▼────────┐         ┌────────▼────────┐
    │  FastAPI App 1  │         │  FastAPI App 2  │
    │   (Container)   │         │   (Container)   │
    └────────┬────────┘         └────────┬────────┘
             │                            │
             └────────────┬───────────────┘
                          │
              ┌───────────▼──────────┐
              │   PostgreSQL DB      │
              │   (Primary/Replica)  │
              └──────────────────────┘
                          │
              ┌───────────▼──────────┐
              │   Cloud Storage      │
              │   (S3/GCS)          │
              └──────────────────────┘
```
