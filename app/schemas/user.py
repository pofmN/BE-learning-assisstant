"""
Pydantic schemas for User model.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr = Field(..., description="User email address")
    username: Optional[str] = Field(None, description="Username of the user")
    full_name: str = Field(..., description="Full name of the user")


class UserCreate(UserBase):
    """Schema for user creation."""

    password: str


class UserUpdate(BaseModel):
    """Schema for user update."""

    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None


class UserInDB(UserBase):
    """Schema for user in database."""

    id: int = Field(..., description="User ID")
    role: str = Field(..., description="Role of the user(student, teacher)")
    is_active: bool = Field(..., description="Indicates if the user is active")
    avatar_url: Optional[str] = Field(None, description="URL of the user's avatar")
    created_at: datetime = Field(..., description="Timestamp when the user was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the user was last updated")

    class Config:
        """Pydantic config."""

        from_attributes = True


class User(UserInDB):
    """Schema for user response."""

    pass


class UserPersonalityInDB(BaseModel):
    """Base schema for user personality."""

    id: int
    user_id: int
    date_of_birth: Optional[int] = Field(None, description="Date of birth in YYYYMMDD(int) format")
    timezone: Optional[str] = Field(None, description="User's timezone")
    about_me: Optional[str] = Field(None, description="About me section")
    school_name: Optional[str] = Field(None, description="Name of the school")
    memories: Optional[str] = Field(None, description="User's memories")
    class Config:
        """Pydantic config."""

        from_attributes = True

class Token(BaseModel):
    """Schema for JWT token."""

    access_token: str
    expires_in: int
    token_type: str


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""

    sub: Optional[int] = None

class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""

    email: EmailStr

class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""

    token: str
    new_password: str