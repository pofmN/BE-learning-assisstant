from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class UserPersonality(Base):
    """Model to store user personality traits."""
    
    __tablename__ = "user_personalities"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    date_of_birth = Column(Integer, nullable=True)  # Stored as YYYYMMDD
    timezone = Column(String, nullable=True)  # E.g., "America/New_York"
    about_me = Column(String, nullable=True)
    school_name = Column(String, nullable=True)
    memories = Column(String, nullable=True)
    # Relationship to User
    user = relationship("User", backref="personality")