from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.services.file_service import FileService
from app.core.document_processor import DocumentProcessor
from app.models.user import User
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseInDB

router = APIRouter()

@router.post("/create", response_model=CourseInDB)
def create_course(
    course: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create a new course.
    """
    file_service = FileService()
    file_content = file_service.get_file_content(gcs_path=course.gcs_path)
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found at the specified GCS path.",
        )
    
    return course