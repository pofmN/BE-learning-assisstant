# Development Guide

## Project Structure

```
DATN/
├── app/                          # Main application code
│   ├── api/                      # API endpoints
│   │   └── v1/                   # API version 1
│   │       ├── auth.py           # Authentication endpoints
│   │       ├── documents.py      # Document management
│   │       ├── mcqs.py           # MCQ generation
│   │       ├── tests.py          # Knowledge testing
│   │       ├── learning.py       # Personalized learning
│   │       └── chat.py           # Virtual teacher WebSocket
│   ├── core/                     # Core functionality
│   │   ├── config.py             # Configuration management
│   │   ├── security.py           # JWT & password utilities
│   │   └── dependencies.py       # Dependency injection
│   ├── db/                       # Database configuration
│   │   ├── base.py               # Database session
│   │   └── init_db.py            # Database initialization
│   ├── models/                   # SQLAlchemy models
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── mcq.py
│   │   ├── test.py
│   │   └── learning.py
│   ├── schemas/                  # Pydantic schemas
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── mcq.py
│   │   ├── test.py
│   │   ├── learning.py
│   │   └── common.py
│   ├── services/                 # Business logic
│   │   └── ai_service.py         # AI model integration
│   ├── utils/                    # Utility functions
│   │   ├── document_parser.py    # Document parsing
│   │   └── file_upload.py        # File upload utilities
│   └── main.py                   # FastAPI application
├── alembic/                      # Database migrations
├── uploads/                      # Uploaded files directory
├── Dockerfile                    # Docker configuration
├── docker-compose.yml            # Docker Compose configuration
├── pyproject.toml                # Poetry dependencies
├── .env.example                  # Environment variables template
└── README.md                     # Project documentation
```

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry package manager
- PostgreSQL (or Docker)
- (Optional) Docker & Docker Compose

### Installation

1. **Clone the repository** (if using Git)

   ```bash
   git clone <your-repo-url>
   cd DATN
   ```

2. **Set up environment variables**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and update configuration as needed.

3. **Install dependencies**

   ```bash
   poetry install
   ```

4. **Start PostgreSQL**

   Using Docker:

   ```bash
   docker-compose up db -d
   ```

   Or install PostgreSQL locally and create database:

   ```sql
   CREATE DATABASE learning_assistant;
   ```

5. **Initialize database**

   ```bash
   poetry run python init_db.py
   ```

6. **Run the application**
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

The API will be available at: http://localhost:8000

API Documentation: http://localhost:8000/docs

### Using Docker Compose

To run everything with Docker:

```bash
docker-compose up --build
```

This will start both PostgreSQL and the FastAPI application.

## Database Migrations

This project uses Alembic for database migrations.

### Create a new migration

After modifying models:

```bash
poetry run alembic revision --autogenerate -m "Description of changes"
```

### Apply migrations

```bash
poetry run alembic upgrade head
```

### Rollback migration

```bash
poetry run alembic downgrade -1
```

## Development Workflow

### 1. Adding a New Feature

Example: Adding a new endpoint

1. **Create/Update Model** (if needed)

   - Add or modify SQLAlchemy model in `app/models/`

2. **Create/Update Schema**

   - Add Pydantic schema in `app/schemas/`

3. **Create Service** (if needed)

   - Add business logic in `app/services/`

4. **Create API Endpoint**

   - Add endpoint in `app/api/v1/`
   - Use appropriate HTTP methods (GET, POST, PUT, DELETE)
   - Add authentication dependency where needed

5. **Test the Endpoint**
   - Use `/docs` to test interactively
   - Or use curl/httpie (see API_EXAMPLES.md)

### 2. Code Style

The project follows PEP8 standards.

**Format code:**

```bash
poetry run black app/
```

**Check code style:**

```bash
poetry run flake8 app/
```

**Type checking:**

```bash
poetry run mypy app/
```

### 3. Testing

Create tests in a `tests/` directory:

```bash
poetry run pytest
```

## Key Components

### Authentication

- JWT-based authentication
- Password hashing with bcrypt
- Protected endpoints use `get_current_active_user` dependency

Example:

```python
@router.get("/protected")
def protected_route(current_user: User = Depends(get_current_active_user)):
    return {"message": f"Hello {current_user.username}"}
```

### Document Processing

Supports PDF, DOCX, and PPTX files:

```python
from app.utils.document_parser import extract_text_from_document

text = extract_text_from_document(file_path, file_type)
```

### AI Service Integration

The `AIService` class in `app/services/ai_service.py` handles AI model interactions:

```python
from app.services.ai_service import ai_service

# Generate MCQs
mcqs = await ai_service.generate_mcqs(text, num_questions=10)

# Chat
response = await ai_service.chat("What is machine learning?")
```

**Note:** The current implementation uses mock responses. Replace with actual AI model API calls in production.

### WebSocket Chat

The virtual teacher chat uses WebSocket for real-time communication:

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/chat/ws?token=YOUR_TOKEN");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.message);
};

ws.send(JSON.stringify({ message: "Hello!" }));
```

## Configuration

Configuration is managed through environment variables in `.env`:

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT secret key (change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time
- `UPLOAD_DIR`: Directory for uploaded files
- `MAX_UPLOAD_SIZE`: Maximum file size in bytes
- `AI_MODEL_URL`: URL for AI model API

## Production Deployment

### 1. Security

- [ ] Change `SECRET_KEY` to a secure random string
- [ ] Set `DEBUG=False`
- [ ] Use HTTPS
- [ ] Set up proper CORS origins
- [ ] Use environment-specific `.env` files
- [ ] Enable rate limiting
- [ ] Set up logging and monitoring

### 2. Database

- [ ] Use a production PostgreSQL server
- [ ] Set up database backups
- [ ] Configure connection pooling
- [ ] Run migrations before deployment

### 3. File Storage

- [ ] Use cloud storage (S3, GCS, etc.) instead of local file system
- [ ] Implement file size and type validation
- [ ] Set up CDN for serving files

### 4. AI Model

- [ ] Deploy AI model to production server
- [ ] Implement proper error handling and fallbacks
- [ ] Add rate limiting for AI API calls
- [ ] Monitor AI model performance

### 5. Deployment Options

**Option 1: Docker**

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Option 2: Cloud Platforms**

- AWS (EC2, ECS, Lambda)
- Google Cloud (Cloud Run, GKE)
- Azure (App Service, Container Instances)
- Heroku, Railway, Render, etc.

**Option 3: Traditional Server**

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Troubleshooting

### Database Connection Errors

1. Check PostgreSQL is running
2. Verify `DATABASE_URL` in `.env`
3. Check network connectivity

### Import Errors

The lint errors you see are normal - they'll resolve after installing dependencies:

```bash
poetry install
```

### File Upload Issues

1. Check `UPLOAD_DIR` exists and is writable
2. Verify `MAX_UPLOAD_SIZE` setting
3. Check file type is in allowed list

### AI Service Errors

The AI service uses mock responses by default. To integrate a real model:

1. Deploy your AI model (T5, GPT, etc.)
2. Update `AI_MODEL_URL` in `.env`
3. Modify `ai_service.py` to call your model API

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linters
4. Submit a pull request

## License

MIT License
