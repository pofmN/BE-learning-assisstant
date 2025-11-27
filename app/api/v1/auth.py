"""
Authentication endpoints for user registration and login.
"""
from datetime import datetime, timedelta
from typing import Any
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_active_user, get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User, PasswordResetToken
from app.schemas.user import Token, User as UserSchema, UserCreate

router = APIRouter()


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> Any:
    """
    Register a new user.

    Args:
        user_in: User registration data
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException: If email or username already exists
    """
    # Check if user exists
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create new user
    user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        role="student",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=Token)
def login(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Login user and return JWT token.

    Args:
        db: Database session
        form_data: OAuth2 form data (username and password)

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user (username can be email or username)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password): # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserSchema)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> Any:
    """
    Get current authenticated user.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user data
    """
    return current_user

@router.get("/forgot-password")
def forgot_password(email, db: Session = Depends(get_db)) -> Any:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )
    token = secrets.token_urlsafe(32)
    exprires_at = datetime.now() + timedelta(hours=1)
    # send email logic hereeee 
    return {"message": "Password reset token generated"}

@router.post("/reset-password")
def reset_password(token: str, new_password: str, db: Session = Depends(get_db)) -> Any:
    # verify token logic
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.expires_at > datetime.now()
    ).first()
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for token",
        )

    # update password and invalidate the reset token
    user.hashed_password = get_password_hash(new_password) # type: ignore
    db.delete(token_record)
    db.add(user)
    db.commit()

    return {"message": "Password has been reset"}
