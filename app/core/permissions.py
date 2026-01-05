"""
Course access control and permissions.

This module provides utilities for checking if a user has access to a course,
either through ownership (uploaded the document) or enrollment (via share link).
"""

from typing import Tuple, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.course import Course, CourseEnrollment, CourseShare
from app.models.document import Document
from app.models.user import User


class CourseAccessLevel:
    """
    Define different access levels for courses.
    
    This makes it easy to check what users can do.
    """
    NONE = "none"           # No access
    VIEW = "view"           # Can view content only (anonymous with public link)
    READ = "read"           # Can view + interact (enrolled users)
    WRITE = "write"         # Can modify course (owners only)


def check_course_access(
    course_id: int,
    user: Optional[User],
    db: Session,
    require_owner: bool = False,
    require_login: bool = False
) -> Tuple[Course, str]:
    """
    Check if user has access to a course and return access level.
    
    This is the MAIN function you should use in all course-related endpoints.
    
    Access hierarchy:
    1. Owner (uploaded document) → WRITE access (can modify)
    2. Enrolled (via share link) → READ access (can view & interact)
    3. Public share link + No login → VIEW access (view only, no interaction)
    4. No relationship → NONE (reject)
    
    Args:
        course_id: ID of the course to check
        user: Current user (can be None for anonymous)
        db: Database session
        require_owner: If True, reject non-owners (for edit/delete operations)
        require_login: If True, reject anonymous users (for interactive operations)
        
    Returns:
        Tuple of (Course object, access_level string)
        
    Raises:
        HTTPException 404: Course not found
        HTTPException 403: User doesn't have access
        HTTPException 401: Login required
        
    Example usage:
        ```python
        # For viewing content (owner OR enrolled OR public)
        course, access = check_course_access(course_id, current_user, db)
        
        # For taking quiz (owner OR enrolled, login required)
        course, access = check_course_access(course_id, current_user, db, require_login=True)
        
        # For editing content (owner ONLY)
        course, access = check_course_access(course_id, current_user, db, require_owner=True)
        ```
    """
    # Step 1: Get course
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID {course_id} not found"
        )
    
    # Step 2: If login required but no user, reject immediately
    if require_login and not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required to access this feature. Please sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Step 3: Check ownership (highest privilege)
    if user:
        document = db.query(Document).filter(
            Document.id == course.document_id,
            Document.owner_id == user.id
        ).first()
        
        is_owner = document is not None
        
        if is_owner:
            return course, CourseAccessLevel.WRITE
        
        # Step 4: If owner required but user is not owner, reject
        if require_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the course creator can perform this action"
            )
        
        # Step 5: Check enrollment (read access)
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.user_id == user.id
        ).first()
        
        if enrollment:
            return course, CourseAccessLevel.READ
    
    # Step 6: Check if course has public share link (view-only for anonymous)
    public_share = db.query(CourseShare).filter(
        CourseShare.course_id == course_id,
        CourseShare.is_public == True
    ).first()
    
    if public_share:
        # Check if link is expired
        from datetime import datetime
        if public_share.expires_at and public_share.expires_at < datetime.now():  # type: ignore
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This course's public share link has expired"
            )
        return course, CourseAccessLevel.VIEW
    
    # Step 7: No access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this course. Please request access from the course creator."
    )


def require_course_access(
    course_id: int, 
    user: Optional[User], 
    db: Session,
    allow_anonymous: bool = False
) -> Course:
    """
    Require user has access to view course content.
    Allows anonymous if course is public.
    
    Use this for READ operations (view content).
    
    Args:
        course_id: ID of the course
        user: Current user (can be None)
        db: Database session
        allow_anonymous: If True, allow public access without login
        
    Returns:
        Course object if user has access
        
    Raises:
        HTTPException: If no access
    """
    require_login = not allow_anonymous
    course, _ = check_course_access(course_id, user, db, require_login=require_login)
    return course


def require_course_interaction(course_id: int, user: User, db: Session) -> Course:
    """
    Require user is logged in and has access to interact with course.
    Used for taking quizzes, reviewing flashcards, etc.
    
    User must be either:
    - Course owner
    - Enrolled user (via share link)
    
    Args:
        course_id: ID of the course
        user: Current user (must not be None)
        db: Database session
        
    Returns:
        Course object if user can interact
        
    Raises:
        HTTPException: If not logged in or no access
    """
    course, access = check_course_access(course_id, user, db, require_login=True)
    
    # VIEW access is not enough for interaction
    if access == CourseAccessLevel.VIEW:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required to interact with this course. Please sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return course


def require_course_ownership(course_id: int, user: User, db: Session) -> Course:
    """
    Verify user is the course owner (document uploader).
    Raises 403 if not owner.
    
    Use this for WRITE operations (edit, delete, share, etc.)
    
    Args:
        course_id: ID of the course
        user: Current user
        db: Database session
        
    Returns:
        Course object if user is owner
        
    Raises:
        HTTPException: If not owner
    """
    course, _ = check_course_access(course_id, user, db, require_owner=True)
    return course


def is_course_owner(course_id: int, user_id: int, db: Session) -> bool:
    """
    Check if a user owns a course (without raising exceptions).
    
    Useful for conditional logic in templates or responses.
    
    Args:
        course_id: ID of the course
        user_id: ID of the user
        db: Database session
        
    Returns:
        True if user owns the course, False otherwise
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return False
    
    document = db.query(Document).filter(
        Document.id == course.document_id,
        Document.owner_id == user_id
    ).first()
    
    return document is not None
