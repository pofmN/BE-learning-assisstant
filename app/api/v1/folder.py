"""Folder management API endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.base import get_db
from app.models.folder import Folder
from app.models.course import Course
from app.models.user import User
from app.schemas.folder import FolderCreate, FolderUpdate, FolderInDB, FolderWithCourseCount
from app.core.dependencies import get_current_active_user

router = APIRouter()


@router.post("/", response_model=FolderInDB, status_code=status.HTTP_201_CREATED)
def create_folder(
    folder: FolderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new folder to organize courses.
    """
    # Create folder
    db_folder = Folder(name=folder.name)
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    
    return db_folder


@router.get("/", response_model=List[FolderWithCourseCount])
def list_folders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all folders with course counts.
    """
    # Query folders with course count
    folders = db.query(
        Folder,
        func.count(Course.id).label("course_count")
    ).outerjoin(
        Course, Folder.id == Course.folder_id
    ).group_by(Folder.id).all()
    
    # Convert to response format
    result = []
    for folder, course_count in folders:
        folder_dict = {
            "id": folder.id,
            "name": folder.name,
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
            "course_count": course_count
        }
        result.append(FolderWithCourseCount(**folder_dict))
    
    return result


@router.get("/{folder_id}", response_model=FolderWithCourseCount)
def get_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific folder with course count.
    """
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder with ID {folder_id} not found"
        )
    
    # Get course count
    course_count = db.query(func.count(Course.id)).filter(
        Course.folder_id == folder_id
    ).scalar()
    
    return FolderWithCourseCount(
        id=folder.id,  # type: ignore
        name=folder.name,  # type: ignore
        created_at=folder.created_at,  # type: ignore
        updated_at=folder.updated_at,  # type: ignore
        course_count=course_count or 0
    )


@router.put("/{folder_id}", response_model=FolderInDB)
def update_folder(
    folder_id: int,
    folder_update: FolderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Rename a folder.
    """
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder with ID {folder_id} not found"
        )
    
    # Update folder name
    folder.name = folder_update.name  # type: ignore
    db.commit()
    db.refresh(folder)
    
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a folder. All courses in the folder will have their folder_id set to NULL.
    """
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder with ID {folder_id} not found"
        )
    
    # Delete folder (courses will have folder_id set to NULL due to ondelete="SET NULL")
    db.delete(folder)
    db.commit()
    
    return None