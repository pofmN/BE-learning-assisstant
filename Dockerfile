FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==1.7.1

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --no-root

COPY . .

RUN mkdir -p /app/uploads

CMD ["sh", "-c", "echo PORT=$PORT && uvicorn app.main:app --host 0.0.0.0 --port $PORT --log-level debug"]
