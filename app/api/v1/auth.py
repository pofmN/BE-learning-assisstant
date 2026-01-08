"""
Authentication endpoints for user registration and login.
"""
from datetime import datetime, timedelta
from typing import Any
import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_active_user, get_db
from app.core.security import create_access_token, get_password_hash, verify_password, create_verification_token
from app.models.user import User, PasswordResetToken
from app.models.user_personality import UserPersonality
from app.schemas.user import Token, User as UserSchema, UserCreate
from app.schemas.auth import ResetPassword
from app.services.mail_service import MailService
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> Any:
    """
    Register a new user with validation and security checks.

    Args:
        user_in: User registration data
        db: Database session

    Returns:
        Created user information

    Raises:
        HTTPException: If validation fails or user already exists
    """

    # Check for existing users
    existing_user = db.query(User).filter(
        (User.email == user_in.email) | (User.username == user_in.username)
    ).first()
    if existing_user:
        if existing_user.email == user_in.email: # type: ignore
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create new user with hashed password
    hashed_password = get_password_hash(user_in.password)
    user = User(
        email=user_in.email.lower().strip(),
        username=user_in.username.strip() if user_in.username else None, # type: ignore
        full_name=user_in.full_name.strip() if user_in.full_name else None,
        hashed_password=hashed_password,
        role="student",
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create user personality after user is committed (so user.id exists)
    user_personality = UserPersonality(user_id=user.id)
    db.add(user_personality)
    db.commit()
    token = create_verification_token(str(user.id), user.email) # type: ignore
    verify_url = f"{settings.FRONTEND_URL}/auth/verify?token={token}"
    await MailService().send_message_background(
        background_tasks,
        subject="Verify your email",
        recipients=[user.email], # type: ignore
        template_name="verify_email.html",
        context={"username": user.username, "verify_url": verify_url}
    )
    logger.info(f"New user registered: {user.username} ({user.email})")
    return user

@router.get("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(
    token: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Verify user email using verification token.

    Args:
        token: Email verification token from email link
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid or expired
    """
    from app.core.security import decode_token
    
    # Decode and validate token
    payload = decode_token(token)
    
    if not payload or payload.get("type") != "email_verification":
        logger.warning("Invalid email verification token attempt")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    
    # Extract user info from token
    user_id = payload.get("sub")
    email = payload.get("email")
    
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token payload",
        )
    
    # Find user and verify
    user = db.query(User).filter(
        User.id == int(user_id),
        User.email == email
    ).first()
    
    if not user:
        logger.error(f"Verification token references non-existent user ID {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check if already verified
    if user.is_active: # type: ignore
        return {"message": "Email already verified"}
    
    # Activate user account
    user.is_active = True # type: ignore
    user.updated_at = datetime.now() # type: ignore
    db.commit()
    
    logger.info(f"Email verified successfully for user: {user.username} ({user.email})")
    
    return {
        "message": "Email verified successfully. You can now login.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }

@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    Authenticate user with secure credential verification and JWT token generation.

    Args:
        request: HTTP request for logging client information
        db: Database session
        form_data: OAuth2 form data containing username and password

    Returns:
        JWT access token with metadata

    Raises:
        HTTPException: If authentication fails
    """
    client_ip = request.client.host if request.client else "unknown"
    username_input = form_data.username.strip().lower()

    # Single efficient query for email or username lookup
    user = db.query(User).filter(
        (User.email.ilike(username_input)) | (User.username == username_input)
    ).first()

    # Use consistent error message to prevent account enumeration
    invalid_credentials_msg = "Invalid username/email or password"

    if not user or not verify_password(form_data.password, user.hashed_password): # type: ignore
        logger.warning(f"Failed login attempt for '{username_input}' from IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=invalid_credentials_msg,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active: # type: ignore
        logger.warning(f"Inactive user login attempt: '{user.username}' from IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Please contact support.",
        )

    # Update last login timestamp
    user.last_login_at = datetime.now()
    db.commit()

    # Generate JWT token with standard claims
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=access_token_expires,
        extra_claims={
            "scope": "user",
            "username": user.username,
            "role": user.role,
        }
    )

    logger.info(f"Successful login for user '{user.username}' from IP {client_ip}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": int(access_token_expires.total_seconds()),
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }
    }


@router.get("/me", response_model=UserSchema)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> Any:
    """
    Retrieve current authenticated user's profile information.

    Args:
        current_user: Currently authenticated user from JWT token

    Returns:
        User profile data
    """
    return current_user


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Any:
    """
    Initiate password reset process by sending reset email.

    Args:
        request: HTTP request for logging
        email: User's email address
        db: Database session
        background_tasks: Background tasks for sending email

    Returns:
        Success message

    Raises:
        HTTPException: If email not found or rate limited
    """
    client_ip = request.client.host if request.client else "unknown"
    email = email.strip().lower()

    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Don't reveal if email exists for security
        logger.info(f"Password reset requested for non-existent email from IP {client_ip}")
        return {"message": "If the email exists, a reset link has been sent."}

    if not user.is_active: # type: ignore
        logger.warning(f"Password reset attempted for inactive user: {email} from IP {client_ip}")
        return {"message": "If the email exists, a reset link has been sent."}

    # Generate secure reset token
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    # Save token to database
    token_record = PasswordResetToken(
        user_id=user.id,
        token=reset_token,
        expires_at=expires_at
    )
    db.add(token_record)
    db.commit()

    # Send reset email
    try:
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        await MailService().send_message_background(
        background_tasks,
        subject="Verify your email",
        recipients=[user.email], # type: ignore
        template_name="verify_email.html",
        context={"username": user.username, "verify_url": reset_link}
    )
        logger.info(f"Password reset email sent to {email} from IP {client_ip}")
    except Exception as e:
        logger.error(f"Failed to send reset email to {email}: {str(e)}")
        # Don't expose email sending errors to client
        pass

    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(
    request: Request,
    reset_info: ResetPassword,
    db: Session = Depends(get_db)
) -> Any:
    """
    Reset user password using valid reset token.

    Args:
        request: HTTP request for logging
        token: Password reset token
        new_password: New password
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid or password requirements not met
    """
    client_ip = request.client.host if request.client else "unknown"

    # Validate password strength
    if len(reset_info.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    # Find and validate token
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == reset_info.token,
        PasswordResetToken.expires_at > datetime.now()
    ).first()

    if not token_record:
        logger.warning(f"Invalid or expired reset token attempt from IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Get user and update password
    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        logger.error(f"Token references non-existent user ID {token_record.user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    # Update password and clean up token
    user.hashed_password = get_password_hash(new_password) # type: ignore
    user.updated_at = datetime.now() # type: ignore
    db.delete(token_record)
    db.commit()

    logger.info(f"Password reset successful for user {user.username} from IP {client_ip}")

    return {"message": "Password has been reset successfully"}
