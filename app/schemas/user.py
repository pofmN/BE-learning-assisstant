"""
Pydantic schemas for User model.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    username: Optional[str] = None
    full_name: str


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

    id: int
    role: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class User(UserInDB):
    """Schema for user response."""

    pass


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