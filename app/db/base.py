"""
Database session and base configuration.
"""
from sqlalchemy import create_engine, event, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure engine with proper pooling for Cloud Run + Supabase
if settings.ENV == "production":
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={
            "options": "-c statement_timeout=30000",
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    )
else:
    # Development: Aggressive settings for Supabase pooler
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=300,  # 5 minutes - CRITICAL for Supabase
        connect_args={
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    )

# Auto-recover from SSL errors
@event.listens_for(engine, "handle_error")
def handle_error(exception_context):
    if "SSL connection has been closed" in str(exception_context.original_exception):
        logger.warning("Stale connection detected, invalidating pool")
        exception_context.is_disconnect = True

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
