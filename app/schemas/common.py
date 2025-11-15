"""
Common schemas for API responses.
"""
from typing import Any, Optional

from pydantic import BaseModel


class Message(BaseModel):
    """Generic message response."""

    message: str


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str


class SuccessResponse(BaseModel):
    """Success response with data."""

    success: bool
    message: str
    data: Optional[Any] = None
