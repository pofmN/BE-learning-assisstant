"""
Database session and base configuration.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Configure engine with proper pooling for Cloud Run + Supabase
# Use NullPool for serverless environments or configure limited pool
if settings.ENV == "production":
    # Production: Use pooler with transaction mode and strict limits
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,  # No connection pooling for serverless
        pool_pre_ping=True,
        connect_args={
            "options": "-c statement_timeout=30000"  # 30s timeout
        }
    )
else:
    # Development: Use small pool
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=3600
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
