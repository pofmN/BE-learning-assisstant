"""
Security utilities for JWT and password hashing.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Internal function to create JWT tokens."""
    now = datetime.now()
    
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type,
        **(extra_claims or {})
    }
    
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Create JWT access token."""
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(subject, "access", delta, extra_claims)


def create_refresh_token(subject: str) -> str:
    """Create JWT refresh token (7 days)."""
    return _create_token(subject, "refresh", timedelta(days=7))


def create_verification_token(subject: str, email: str) -> str:
    """Create email verification token (24 hours)."""
    return _create_token(subject, "email_verification", timedelta(hours=24), {"email": email})


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT token."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)
