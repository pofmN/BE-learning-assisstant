# 🎓 Intelligent Learning Assistant - Project Summary

## Overview

This is a production-ready FastAPI backend system that helps university students study more effectively using AI. The system supports document-based learning, automatic MCQ generation, real-time evaluation, and personalized learning recommendations.

## ✨ Features Implemented

### 1. **Authentication System** ✅

- JWT-based authentication
- User registration and login
- Password hashing with bcrypt
- Role-based access (student, admin)
- Protected endpoints

**Files:**

- `app/api/v1/auth.py` - Authentication endpoints
- `app/core/security.py` - JWT & password utilities
- `app/core/dependencies.py` - Auth dependencies

### 2. **Document Management** ✅

- Upload PDF, DOCX, PPTX files
- Automatic text extraction
- File metadata storage
- Document CRUD operations
- User-owned documents

**Files:**

- `app/api/v1/documents.py` - Document endpoints
- `app/utils/document_parser.py` - Text extraction
- `app/utils/file_upload.py` - File handling

### 3. **MCQ Generation Pipeline** ✅

- Generate MCQs from documents using AI
- Structured JSON output (question, choices, answer, explanation)
- Configurable difficulty and topics
- Database storage of generated MCQs

**Files:**

- `app/api/v1/mcqs.py` - MCQ endpoints
- `app/services/ai_service.py` - AI integration (mock implementation)

### 4. **Knowledge Testing** ✅

- Submit test answers
- Automatic evaluation
- Score calculation
- Detailed feedback
- Test history

**Files:**

- `app/api/v1/tests.py` - Testing endpoints
- `app/models/test.py` - Test models

### 5. **Personalized Learning** ✅

- Track user progress by topic
- Analyze weak areas
- Generate personalized recommendations
- Learning analytics

**Files:**

- `app/api/v1/learning.py` - Learning endpoints
- `app/models/learning.py` - Learning progress model

### 6. **Virtual Teacher (WebSocket)** ✅

- Real-time chat via WebSocket
- Interactive Q&A
- Context-aware responses
- Streaming support

**Files:**

- `app/api/v1/chat.py` - WebSocket chat endpoint

## 🗄️ Database Schema

### Models Created:

1. **User** - Authentication and user management
2. **Document** - Uploaded files and extracted text
3. **MCQ** - Multiple choice questions
4. **TestResult** - Test submissions and scores
5. **TestAnswer** - Individual question answers
6. **LearningProgress** - User progress tracking

## 📁 Project Structure

```
DATN/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Configuration & security
│   ├── db/              # Database setup
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic (AI service)
│   ├── utils/           # Utilities (parsing, upload)
│   └── main.py          # FastAPI app
├── alembic/             # Database migrations
├── uploads/             # Uploaded files
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose
├── pyproject.toml       # Poetry dependencies
├── .env.example         # Environment template
├── README.md            # Documentation
├── DEVELOPMENT.md       # Developer guide
└── API_EXAMPLES.md      # API usage examples
```

## 🚀 Quick Start

### Option 1: Using Poetry (Recommended)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Install dependencies
poetry install

# 3. Start PostgreSQL
docker-compose up db -d

# 4. Initialize database
poetry run python init_db.py

# 5. Run application
poetry run uvicorn app.main:app --reload
```

### Option 2: Using Docker Compose

```bash
# Copy environment file
cp .env.example .env

# Start everything
docker-compose up --build
```

### Option 3: Windows PowerShell Script

```powershell
.\setup.ps1
```

**Access the application:**

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📋 API Endpoints

### Authentication

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user
- `GET /api/v1/auth/me` - Get current user

### Documents

- `POST /api/v1/documents/upload` - Upload document
- `GET /api/v1/documents` - List documents
- `GET /api/v1/documents/{id}` - Get document
- `DELETE /api/v1/documents/{id}` - Delete document

### MCQ Generation

- `POST /api/v1/mcqs/generate` - Generate MCQs
- `GET /api/v1/mcqs` - List MCQs
- `GET /api/v1/mcqs/{id}` - Get MCQ

### Knowledge Testing

- `POST /api/v1/tests/submit` - Submit test
- `GET /api/v1/tests/results` - Get test results
- `GET /api/v1/tests/results/{id}` - Get specific result

### Personalized Learning

- `GET /api/v1/learning/progress` - Get progress
- `GET /api/v1/learning/recommendations` - Get recommendations
- `GET /api/v1/learning/weak-areas` - Get weak areas

### Virtual Teacher

- `WS /api/v1/chat/ws` - WebSocket chat

## 🔧 Configuration

Key environment variables in `.env`:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/learning_assistant
SECRET_KEY=your-super-secret-key-change-this
ACCESS_TOKEN_EXPIRE_MINUTES=30
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=10485760
AI_MODEL_URL=http://localhost:8001/generate
```

## 🎯 Next Steps for Production

### 1. **AI Model Integration**

The current implementation uses mock responses. You need to:

- Deploy your fine-tuned T5 model or connect to an LLM API
- Update `app/services/ai_service.py` with real API calls
- Add error handling and retry logic

Example integration:

```python
async def generate_mcqs(self, text: str, num_questions: int):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            self.model_url,
            json={"text": text, "num_questions": num_questions},
            timeout=self.timeout
        )
        return response.json()
```

### 2. **Security Enhancements**

- Change `SECRET_KEY` to a secure random string
- Set up HTTPS
- Implement rate limiting
- Add input validation and sanitization
- Set up logging and monitoring

### 3. **Database**

- Run migrations: `poetry run alembic upgrade head`
- Set up database backups
- Configure connection pooling
- Use production PostgreSQL server

### 4. **File Storage**

- Replace local storage with cloud storage (S3, GCS)
- Implement virus scanning for uploads
- Add CDN for serving files

### 5. **Testing**

- Write unit tests
- Add integration tests
- Set up CI/CD pipeline

### 6. **Deployment**

- Use Docker Compose for production
- Or deploy to cloud (AWS, GCP, Azure)
- Set up load balancing
- Configure auto-scaling

## 📚 Documentation

- **README.md** - Project overview and quick start
- **DEVELOPMENT.md** - Comprehensive developer guide
- **API_EXAMPLES.md** - API usage examples with curl
- **Interactive Docs** - http://localhost:8000/docs

## 🧪 Testing

Test the setup:

```bash
poetry run python test_setup.py
```

Test API endpoints:

- Use the interactive docs at `/docs`
- See `API_EXAMPLES.md` for curl examples

## 🛠️ Tech Stack

- **Framework:** FastAPI 0.109+
- **Database:** PostgreSQL + SQLAlchemy 2.0
- **Authentication:** JWT (python-jose) + bcrypt
- **Document Parsing:** PyPDF2, python-docx, python-pptx
- **Validation:** Pydantic 2.5+
- **WebSockets:** Native FastAPI WebSocket support
- **Migrations:** Alembic
- **Containerization:** Docker + Docker Compose

## ✅ Code Quality

- **PEP8 compliant** - Follows Python style guidelines
- **Type hints** - Using Python type annotations
- **Modular structure** - Clean separation of concerns
- **Error handling** - Global exception handlers
- **CORS enabled** - Ready for frontend integration
- **Documented** - Comprehensive docstrings

## 🐛 Known Limitations

1. **AI Service** - Currently using mock responses. Requires real model integration.
2. **WebSocket Auth** - Simplified authentication. Needs proper JWT validation.
3. **File Storage** - Using local file system. Should use cloud storage in production.
4. **Testing** - No automated tests yet. Should be added.

## 📝 Default Admin Account

After running `init_db.py`, a default admin account is created:

- Email: `admin@example.com`
- Password: `admin123`

**⚠️ Change this in production!**

## 🤝 Contributing

1. Follow PEP8 style guidelines
2. Add type hints to all functions
3. Write docstrings for all public functions
4. Format code with Black: `poetry run black app/`
5. Run linters: `poetry run flake8 app/`

## 📄 License

MIT License

---

**Built with ❤️ for university students to enhance their learning experience!**
