"""
Database initialization and seeding.
"""
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User


def init_db(db: Session) -> None:
    """
    Initialize database with default data.

    Args:
        db: Database session
    """
    # Check if admin user exists
    admin = db.query(User).filter(User.email == "admin@example.com").first()
    if not admin:
        admin = User(
            email="admin@example.com",
            username="admin",
            full_name="System Administrator",
            hashed_password=get_password_hash("admin123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("Admin user created successfully")
