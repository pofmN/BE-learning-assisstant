from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Request
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_active_user
from app.db.base import get_db, SessionLocal
from app.models.user import User
from app.models.course import Course, CourseSection
from app.models.document import Document
from app.core.agents.course.course_manager import CourseManagerAgent
from app.schemas.course import CourseCreate, CourseInDB, CourseCreateResponse, CourseSectionInDB
from pydantic import BaseModel
import logging
import os
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import json
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class CourseTaskQueue:
    """Google Cloud Tasks helper for course generation."""
    
    def __init__(self):
        self.is_local = os.getenv('ENV', 'local') == 'local'
        if not self.is_local:
            self.client = tasks_v2.CloudTasksClient()
            self.project = settings.GCS_PROJECT_ID
            self.location = 'asia-southeast1'
            self.queue = 'course-processing'  # New queue for courses
        
    def enqueue_course_generation(
        self,
        course_id: int,
        course_config: CourseCreate,
        delay_seconds: int = 0
    ):
        """Enqueue a course generation task."""
        
        # For local development, process synchronously
        if self.is_local:
            logger.info(f"LOCAL ENV: Generating course {course_id} synchronously")
            db = SessionLocal()
            try:
                generate_course_task(course_id, course_config.dict(), db)
            finally:
                db.close()
            return "local-sync-processing"
        
        # For cloud, use Cloud Tasks
        parent = self.client.queue_path(self.project, self.location, self.queue)
        
        # Construct the request body
        payload = {
            'course_id': course_id,
            'course_config': course_config.dict()
        }
        
        # Construct the task
        task = {
            'http_request': {
                'http_method': tasks_v2.HttpMethod.POST,
                'url': f'{settings.BACKEND_URL}/api/v1/course/internal/generate-course',
                'headers': {
                    'Content-Type': 'application/json',
                },
                'body': json.dumps(payload).encode()
            }
        }
        
        # Add delay if specified
        if delay_seconds > 0:
            d = datetime.now() + timedelta(seconds=delay_seconds)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(d)
            task['schedule_time'] = timestamp  # type: ignore
        
        # Create the task
        response = self.client.create_task(
            request={'parent': parent, 'task': task}
        )
        
        logger.info(f'Created task {response.name} for course {course_id}')
        return response.name


def generate_course_task(course_id: int, course_config_dict: dict, db: Session):
    """
    Task to generate course content.
    Used by both Cloud Tasks and local development.
    """
    try:
        logger.info(f"Starting course generation for course ID {course_id}")
        
        # Update status to processing
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            logger.error(f"Course {course_id} not found")
            return
        
        course.status = "processing"  # type: ignore
        db.commit()
        
        # Reconstruct CourseCreate from dict
        course_config = CourseCreate(**course_config_dict)
        
        # Generate course
        agent = CourseManagerAgent(db=db)
        result = agent.run(course_id=course_id, course_config=course_config)
        
        if result.get("error"):
            logger.error(f"Course generation failed for course {course_id}: {result.get('error')}")
            course.status = "failed"  # type: ignore
            db.commit()
        else:
            logger.info(f"Course generation completed for course ID {course_id}")
            # Status is set to "completed" by CourseManagerAgent
            
    except Exception as e:
        logger.error(f"Error generating course ID {course_id}: {e}")
        course = db.query(Course).filter(Course.id == course_id).first()
        if course:
            course.status = "failed"  # type: ignore
            db.commit()


@router.post("/internal/generate-course")
async def internal_generate_course(request: Request):
    """
    Internal endpoint called by Cloud Tasks to generate course.
    Should NOT be exposed publicly in production.
    """
    payload = await request.json()
    course_id = payload.get('course_id')
    course_config_dict = payload.get('course_config')
    
    if not course_id or not course_config_dict:
        raise HTTPException(status_code=400, detail="Missing course_id or course_config")
    
    logger.info(f"Processing course {course_id} from Cloud Tasks")
    
    db = SessionLocal()
    try:
        generate_course_task(course_id, course_config_dict, db)
        return {"status": "success", "course_id": course_id}
    finally:
        db.close()


@router.post("/create", response_model=CourseCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_course(
    course: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create a new course from a document (async).
    
    Returns immediately with course_id and status="queued".
    Course content is generated via Cloud Tasks.
    Poll GET /courses/{course_id}/status to check completion status.
    """
    document_id = course.document_id
    document = db.query(Document).filter(
        Document.id == document_id, 
        Document.owner_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    # Check if document is processed
    if document.status != "processed": # type: ignore
        raise HTTPException(
            status_code=400, 
            detail=f"Document must be fully processed before creating a course. Current status: {document.status}"
        )
    
    # Convert question_type list to comma-separated string for database
    question_type_str = ','.join(course.question_type) if course.question_type else None
    
    # Create course immediately with status="queued"
    new_course = Course(
        document_id=document_id,
        title="Processing...",
        description="Course is being generated",
        language=course.language,
        level=course.level,
        requirements=course.requirements,
        question_type=question_type_str,  # Store as comma-separated string
        status="queued"  # Changed from "processing"
    )
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    
    # Queue task with Cloud Tasks
    try:
        task_queue = CourseTaskQueue()
        task_queue.enqueue_course_generation(
            course_id=new_course.id,  # type: ignore
            course_config=course
        )
        logger.info(f"Course ID '{new_course.id}' queued for generation")
    except Exception as e:
        logger.error(f"Failed to queue course generation task: {e}")
        new_course.status = "failed"  # type: ignore
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to queue course generation: {str(e)}")
    
    return CourseCreateResponse(
        course_id=new_course.id,  # type: ignore
        status="queued",
        message="Course generation queued. Poll GET /courses/{course_id}/status to check status."
    )


@router.get("/{course_id}/status", response_model=CourseInDB)
def get_course_status(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get course by ID.
    Status can be: "queued", "processing", "completed", or "failed"
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


@router.get("/{course_id}/sections", response_model=List[CourseSectionInDB])
def get_course_sections(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve sections associated with a specific course.
    
    Args:
        course_id: ID of the course
        db: Database session

    Returns:
        List of course sections
    """
    
    sections = db.query(CourseSection).filter(CourseSection.course_id == course_id).all()
    if not sections:
        raise HTTPException(status_code=404, detail="No sections found for this course.")
    return sections

@router.get("/", response_model=List[CourseInDB])
def list_user_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    List all courses for the current user.
    """
    courses = db.query(Course).join(Document).filter(Document.owner_id == current_user.id).all()
    return courses

@router.post("/{course_id}/modify")
def modify_course(
    course_id: int,
    course_update: CourseInDB,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Modify an existing course by re-generating its content.
    
    Args:
        course_id: ID of the course to modify
        course_update: New course configuration
        db: Database session
        current_user: Currently authenticated user
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    # Verify ownership through document
    document = db.query(Document).filter(Document.id == course.document_id, Document.owner_id == current_user.id).first()
    if not document:
        raise HTTPException(status_code=403, detail="Not authorized to modify this course")

    try:
        modified_course = Course(
            document_id=course.document_id,
            title=course_update.title,
            description=course_update.description,
        )
        db.add(modified_course)
        db.commit()
        db.refresh(modified_course)
        logger.info(f"Updating course ID '{course_id}'")
    except Exception as e:
        logger.error(f"Failed to modify course '{course_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to modify course: {str(e)}")

    return CourseCreateResponse(
        course_id=course.id,  # type: ignore
        status="completed",
        message="Course modification completed successfully."
    )