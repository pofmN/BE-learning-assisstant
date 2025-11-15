# Setup script for Windows (PowerShell)

Write-Host "Setting up Intelligent Learning Assistant..." -ForegroundColor Green

# Copy environment file
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "✅ Created .env file" -ForegroundColor Green
}

# Install dependencies with Poetry
Write-Host "Installing dependencies..." -ForegroundColor Yellow
poetry install

# Start PostgreSQL with Docker
Write-Host "Starting PostgreSQL..." -ForegroundColor Yellow
docker-compose up db -d

# Wait for PostgreSQL to be ready
Write-Host "Waiting for database to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Initialize database
Write-Host "Initializing database..." -ForegroundColor Yellow
poetry run python init_db.py

Write-Host ""
Write-Host "🎉 Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Cyan
Write-Host "  poetry run uvicorn app.main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "Or use Docker Compose:" -ForegroundColor Cyan
Write-Host "  docker-compose up" -ForegroundColor White
Write-Host ""
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Cyan
