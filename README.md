# Intelligent Learning Assistant with Interaction and Knowledge Testing

A production-ready FastAPI backend system that helps university students study more effectively using AI. Supports document-based learning, automatic MCQ generation, real-time evaluation, and personalized learning recommendations.

## Features

- 📄 **Document Management**: Upload and parse PDF, DOCX, PPTX files
- 🎯 **MCQ Generation**: Automatically generate multiple-choice questions from learning materials
- ✅ **Knowledge Testing**: Real-time evaluation with scoring and feedback
- 🎓 **Personalized Learning**: Track progress and get recommendations
- 💬 **Virtual Teacher**: Interactive Q&A via WebSocket
- 🔐 **Authentication**: JWT-based user management

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL + SQLAlchemy ORM
- **Authentication**: JWT + bcrypt
- **Document Parsing**: PyPDF2, python-docx, python-pptx
- **Real-time**: WebSockets
- **Containerization**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry 2.0+
- Docker & Docker Compose
- Docker Desktop (for Windows)

### Installation

1. **Clone the repository**

```bash
git clone <your-repo-url>
cd DATN
```

2. **Install Poetry** (if not already installed)

```powershell
# For Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

3. **Copy environment file**

```bash
cp .env.example .env
```

Edit `.env` and update the configuration as needed.

4. **Install dependencies**

```bash
poetry install
```

5. **Start PostgreSQL with Docker**

Make sure Docker Desktop is running, then:

```bash
docker-compose up db -d
```

6. **Run database migrations**

```bash
poetry run alembic upgrade head
```

7. **Start the application**

```bash
poetry run uvicorn app.main:app --reload
```

The API will be available at: http://localhost:8000

API Documentation: http://localhost:8000/docs

### Using Docker (Full Stack)

```bash
docker-compose up --build
```

### Activating Poetry Environment

To run commands without the `poetry run` prefix:

```bash
# Activate the environment (Poetry 2.0+)
poetry env info --path
# Copy the path and activate manually:
# Windows PowerShell:
& "C:\Users\ADMIN\AppData\Local\pypoetry\Cache\virtualenvs\datn-Qh1lQVe4-py3.11\Scripts\Activate.ps1"
```

Or simply use `poetry run` before every command:

```bash
poetry run uvicorn app.main:app --reload
poetry run alembic upgrade head
poetry run pytest
```

## Project Structure

```
DATN/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py          # Authentication endpoints
│   │       ├── documents.py     # Document management
│   │       ├── mcqs.py          # MCQ generation
│   │       ├── tests.py         # Knowledge testing
│   │       ├── learning.py      # Personalized learning
│   │       └── chat.py          # Virtual teacher WebSocket
│   ├── core/
│   │   ├── config.py            # Configuration management
│   │   ├── security.py          # JWT & password utilities
│   │   └── dependencies.py      # Dependency injection
│   ├── db/
│   │   ├── base.py              # Database base & session
│   │   └── init_db.py           # Database initialization
│   ├── models/                   # SQLAlchemy models
│   ├── schemas/                  # Pydantic schemas
│   ├── services/                 # Business logic
│   ├── utils/                    # Utility functions
│   └── main.py                   # FastAPI application
├── alembic/                      # Database migrations
├── uploads/                      # Uploaded files directory
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml               # Poetry dependencies
├── poetry.lock                  # Locked dependencies
└── .env.example                 # Environment variables template
```

## API Endpoints

### Authentication

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user
- `GET /api/v1/auth/me` - Get current user

### Documents

- `POST /api/v1/documents/upload` - Upload document
- `GET /api/v1/documents` - List user documents
- `GET /api/v1/documents/{id}` - Get document details
- `DELETE /api/v1/documents/{id}` - Delete document

### MCQ Generation

- `POST /api/v1/mcqs/generate` - Generate MCQs from document
- `GET /api/v1/mcqs` - List MCQs
- `GET /api/v1/mcqs/{id}` - Get MCQ details

### Knowledge Testing

- `POST /api/v1/tests/submit` - Submit test answers
- `GET /api/v1/tests/results` - Get test results
- `GET /api/v1/tests/results/{id}` - Get specific result

### Personalized Learning

- `GET /api/v1/learning/progress` - Get learning progress
- `GET /api/v1/learning/recommendations` - Get topic recommendations
- `GET /api/v1/learning/weak-areas` - Get weak areas analysis

### Virtual Teacher

- `WS /api/v1/chat/ws` - WebSocket for interactive Q&A

## Development

### Common Commands

```bash
# Run the development server
poetry run uvicorn app.main:app --reload

# Run database migrations
poetry run alembic upgrade head

# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Run tests
poetry run pytest

# Format code
poetry run black app/

# Check types
poetry run mypy app/
```

### Adding Dependencies

```bash
# Add a new package
poetry add package-name

# Add a dev dependency
poetry add --group dev package-name
```

### Code Style

The project follows PEP8 standards. Format code using:

```bash
poetry run black app/
```

### Testing

```bash
poetry run pytest
```

## Environment Variables

See `.env.example` for all available configuration options:

- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT secret key
- `ALGORITHM` - JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time

## Troubleshooting

### Docker Desktop not running

Make sure Docker Desktop is running before executing `docker-compose` commands.

### Port already in use

If port 8000 is already in use, change it in `docker-compose.yml` or when running uvicorn:

```bash
poetry run uvicorn app.main:app --reload --port 8001
```

### Database connection errors

Ensure PostgreSQL is running and the `DATABASE_URL` in `.env` is correct.

## License

MIT License
