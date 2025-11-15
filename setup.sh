#!/bin/bash

# Setup script for Linux/Mac

echo "Setting up Intelligent Learning Assistant..."

# Copy environment file
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file"
fi

# Install dependencies with Poetry
echo "Installing dependencies..."
poetry install

# Start PostgreSQL with Docker
echo "Starting PostgreSQL..."
docker-compose up db -d

# Wait for PostgreSQL to be ready
echo "Waiting for database to be ready..."
sleep 5

# Initialize database
echo "Initializing database..."
poetry run python init_db.py

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start the application:"
echo "  poetry run uvicorn app.main:app --reload"
echo ""
echo "Or use Docker Compose:"
echo "  docker-compose up"
echo ""
echo "API Documentation: http://localhost:8000/docs"
