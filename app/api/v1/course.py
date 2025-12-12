from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.user import User
from app.models.course import Course
from app.models.document import Document
from app.core.agents.course_manager import CourseManagerAgent
from app.schemas.course import CourseCreate, CourseInDB, CourseCreateResponse
from pydantic import BaseModel

router = APIRouter()


def generate_course_background(course_id: int, course_config: CourseCreate, db: Session):
    """Background task to generate course content."""
    try:
        agent = CourseManagerAgent(db=db)
        result = agent.run(course_id=course_id, course_config=course_config)
        
        if result.get("error"):
            # Update course status to failed
            course = db.query(Course).filter(Course.id == course_id).first()
            if course:
                course.status = "failed" #type: ignore
                db.commit()
    except Exception as e:
        # Handle errors and update status
        course = db.query(Course).filter(Course.id == course_id).first()
        if course:
            course.status = "failed" #type: ignore
            db.commit()
        raise


# In app/api/v1/course.py, update the create_course function:

@router.post("/create", response_model=CourseCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_course(
    course: CourseCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create a new course from a document (async).
    
    Returns immediately with course_id and status="processing".
    Course content is generated in the background.
    Poll GET /courses/{course_id} to check completion status.
    """
    document_id = course.document_id
    document = db.query(Document).filter(
        Document.id == document_id, 
        Document.owner_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    # Convert question_type list to comma-separated string for database
    question_type_str = ','.join(course.question_type) if course.question_type else None
    
    # Create course immediately with status="processing"
    new_course = Course(
        document_id=document_id,
        title="Processing...",
        description="Course is being generated",
        language=course.language,
        level=course.level,
        requirements=course.requirements,
        question_type=question_type_str,  # Store as comma-separated string
        status="processing"
    )
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    
    # Queue background task
    background_tasks.add_task(
        generate_course_background,
        course_id=new_course.id, #type: ignore
        course_config=course,
        db=db
    )
    
    return CourseCreateResponse(
        course_id=new_course.id, #type: ignore
        status="processing",
        message="Course generation started. Poll GET /courses/{course_id} to check status."
    )


@router.get("/{course_id}/status", response_model=CourseInDB)
def get_course_status(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get course by ID.
    Status can be: "processing", "completed", or "failed"
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Verify ownership through document
    document = db.query(Document).filter(
        Document.id == course.document_id,
        Document.owner_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=403, detail="Not authorized to access this course")
    
    return course