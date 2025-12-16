from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_db
from app.models.course import StudiesNote
from app.schemas.course import StudiesNoteInDB


router = APIRouter()


@router.get("/section/{section_id}", response_model=List[StudiesNoteInDB])
def get_studies_notes_by_section(
    section_id: int,
    db: Session = Depends(get_db),
    #current_user: Any = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve study notes associated with a specific course section.
    
    Args:
        section_id: ID of the course section
        db: Database session

    Returns:
        List of study notes for the specified section
    """
    
    notes = db.query(StudiesNote).filter(StudiesNote.section_id == section_id).all()
    if not notes:
        raise HTTPException(status_code=404, detail="No study notes found for this course section.")
    return notes

@router.get("/course/{course_id}", response_model=List[StudiesNoteInDB])
def get_studies_notes_by_course(
    course_id: int,
    db: Session = Depends(get_db),
    #current_user: Any = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve study notes associated with a specific course.
    
    Args:
        course_id: ID of the course
        db: Database session

    Returns:
        List of study notes for the specified course
    """
    
    notes = db.query(StudiesNote).filter(StudiesNote.course_id == course_id).all()
    if not notes:
        raise HTTPException(status_code=404, detail="No study notes found for this course.")
    return notes