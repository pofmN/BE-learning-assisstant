"""
Script to initialize the database with tables and seed data.
"""
from app.db.base import Base, engine, SessionLocal
from app.db.init_db import init_db


def init() -> None:
    """Initialize database."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

    print("Seeding initial data...")
    db = SessionLocal()
    try:
        init_db(db)
        print("✅ Initial data seeded")
    finally:
        db.close()

    print("🎉 Database initialization complete!")


if __name__ == "__main__":
    init()
