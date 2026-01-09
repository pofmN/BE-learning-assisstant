# Add these imports at the top

import secrets
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Any, List
from sqlalchemy.orm import Session
from app.models.course import CourseShare, CourseEnrollment
from app.schemas.course import (
    CourseShareCreate, 
    CourseShareResponse, 
    CourseEnrollmentResponse,
    CourseWithAccess,
    CourseShareList
)
from app.core.config import settings
from app.schemas.course import CourseInDB
from app.models.document import Document
from app.models.user import User
from app.models.course import Course
from app.core.dependencies import get_current_active_user, get_db, get_current_user_optional
from app.core.permissions import require_course_ownership

logger = logging.getLogger(__name__)

router = APIRouter()

# ============= COURSE SHARING ENDPOINTS =============

@router.post("/{course_id}/share", response_model=CourseShareResponse, status_code=status.HTTP_201_CREATED)
def create_share_link(
    course_id: int,
    share_data: CourseShareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create a shareable link for a course (owner only).
    
    This endpoint allows course owners to generate a unique shareable link.
    
    Process:
    1. Verify course exists
    2. Verify user owns the course (via Document ownership)
    3. Generate cryptographically secure token
    4. Calculate expiration date if specified
    5. Store share link in database
    6. Return full URL for frontend
    
    Args:
        course_id: ID of the course to share
        share_data: Share configuration (public flag, expiration)
        db: Database session
        current_user: Authenticated user (must be course owner)
        
    Returns:
        Share link with full URL and metadata
        
    """
    # Verify ownership: Only owner can create share links
    course = require_course_ownership(course_id, current_user, db)
    
    # Step 3: Generate unique share token
    # secrets.token_urlsafe() generates cryptographically strong random token
    # 32 bytes = 64 characters in base64url encoding
    share_token = secrets.token_urlsafe(32)
    
    # Step 4: Calculate expiration date
    expires_at = None
    if share_data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=share_data.expires_in_days)
    
    # Step 5: Create share record
    course_share = CourseShare(
        course_id=course_id,
        share_token=share_token,
        is_public=share_data.is_public,
        created_by=current_user.id,  # type: ignore
        expires_at=expires_at
    )
    
    db.add(course_share)
    try:
        db.commit()
        db.refresh(course_share)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating share link: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create share link"
        )
    
    # Step 6: Construct full URL
    # In production, replace with your actual domain
    base_url = settings.FRONTEND_URL or "http://localhost:3000"
    share_url = f"{base_url}/courses/shared/{share_token}"
    
    logger.info(f"User {current_user.id} created share link for course {course_id}: {share_token}")
    
    return CourseShareResponse(
        id=course_share.id,  # type: ignore
        course_id=course_share.course_id,  # type: ignore
        share_token=course_share.share_token,  # type: ignore
        share_url=share_url,
        is_public=course_share.is_public,  # type: ignore
        expires_at=course_share.expires_at,  # type: ignore
        created_at=course_share.created_at  # type: ignore
    )


@router.get("/shared/{share_token}", response_model=CourseInDB)
def access_shared_course(
    share_token: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Any:
    """
    Access a course via share link.
    
    This is a PUBLIC endpoint that works for both anonymous and logged-in users.
    
    Access control logic:
    - Public link + Anonymous user → View-only access (can see content, can't take quizzes)
    - Public link + Logged-in user → Auto-enroll + Full access
    - Private link + Anonymous user → 401 Error (must login)
    - Private link + Logged-in user → Auto-enroll + Full access
    
    Why auto-enroll?
    - Once enrolled, user can access course without share link
    - Enrollment persists even if share link expires
    - Creates permanent relationship between user and course
    
    Args:
        share_token: The unique share token from URL
        db: Database session
        current_user: Optional authenticated user
        
    Returns:
        Course data with sections, quizzes, etc.
        
    Raises:
        404: Share link not found
        410: Share link expired
        401: Private link requires login
    """
    # Step 1: Find share link
    share = db.query(CourseShare).filter(
        CourseShare.share_token == share_token
    ).first()
    
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid share link. This link may have been deleted."
        )
    
    # Step 2: Check expiration
    if share.expires_at and share.expires_at < datetime.now(timezone.utc): # type: ignore
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has expired. Please request a new link from the course creator."
        )
    
    # Step 3: Check if login is required (private link)
    if not share.is_public and not current_user:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required to access this course. Please sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Step 3.5: Check if logged-in user is authorized for private link
    if not share.is_public and current_user:  # type: ignore
        # Check if user is already enrolled or is the owner
        is_owner = db.query(Course).join(Document).filter(
            Course.id == share.course_id,  # type: ignore
            Document.user_id == current_user.id
        ).first() is not None
        
        is_enrolled = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == share.course_id  # type: ignore
        ).first() is not None
        
        if not is_owner and not is_enrolled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this private course. Please contact the course owner for access."
            )

    # Step 4: Auto-enroll logged-in users (ONLY FOR PUBLIC LINKS)
    if current_user and share.is_public:  # type: ignore - Add is_public check
        # Check if already enrolled
        existing_enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == share.course_id  # type: ignore
        ).first()
        
        # Create enrollment if not exists
        if not existing_enrollment:
            enrollment = CourseEnrollment(
                user_id=current_user.id,  # type: ignore
                course_id=share.course_id,  # type: ignore
                enrolled_via="share_link"
            )
            db.add(enrollment)
            try:
                db.commit()
                logger.info(f"User {current_user.id} enrolled in course {share.course_id} via share link")
            except Exception as e:
                db.rollback()
                logger.error(f"Error enrolling user: {e}")
                # Don't fail the request if enrollment fails
    
    # Step 5: Get and return course
    course = db.query(Course).filter(Course.id == share.course_id).first()  # type: ignore
    
    if not course:
        # This shouldn't happen due to foreign key, but handle it
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    logger.info(f"Course {course.id} accessed via share link by user {current_user.id if current_user else 'anonymous'}")
    
    return course

@router.patch("/{course_id}/shares/{share_id}", response_model=CourseShareResponse)
def update_share_link(
    course_id: int,
    share_id: int,
    update_data: CourseShareCreate,  # Reuse same schema
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update share link settings (owner only).
    
    Allows changing:
    - is_public: Switch between public/private
    - expires_in_days: Extend or shorten expiration, null or remove this field for case no expiration.
    
    Note: Changing is_public does NOT affect already-enrolled users.
    They retain access via enrollment table, not share link.
    """
    course = require_course_ownership(course_id, current_user, db)
    
    share = db.query(CourseShare).filter(
        CourseShare.id == share_id,
        CourseShare.course_id == course_id
    ).first()
    
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    
    # Update fields
    share.is_public = update_data.is_public  # type: ignore
    
    if update_data.expires_in_days:
        share.expires_at = datetime.now(timezone.utc) + timedelta(days=update_data.expires_in_days)  # type: ignore
    else:
        share.expires_at = None  # type: ignore
    
    db.commit()
    db.refresh(share)
    
    base_url = settings.FRONTEND_URL or "http://localhost:3000"
    share_url = f"{base_url}/courses/shared/{share.share_token}"  # type: ignore
    
    logger.info(f"User {current_user.id} updated share link {share_id} for course {course_id}")
    
    return CourseShareResponse(
        id=share.id,  # type: ignore
        course_id=share.course_id,  # type: ignore
        share_token=share.share_token,  # type: ignore
        share_url=share_url,
        is_public=share.is_public,  # type: ignore
        expires_at=share.expires_at,  # type: ignore
        created_at=share.created_at  # type: ignore
    )


@router.get("/{course_id}/shares", response_model=List[CourseShareList])
def list_course_shares(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    List all share links for a course (owner only).
    
    This allows course owners to:
    - See all active share links
    - Check expiration dates
    - Audit who created which links
    
    Args:
        course_id: ID of the course
        db: Database session
        current_user: Authenticated user (must be course owner)
        
    Returns:
        List of share links with metadata
        
    Raises:
        404: Course not found
        403: User is not the course owner
    """
    # Verify ownership: Only owner can list share links
    course = require_course_ownership(course_id, current_user, db)
    
    # Get all shares
    shares = db.query(CourseShare).filter(
        CourseShare.course_id == course_id
    ).all()
    
    # Build response
    base_url = settings.FRONTEND_URL or "http://localhost:3000"
    
    result = []
    for share in shares:
        result.append(CourseShareList(
            id=share.id,  # type: ignore
            share_token=share.share_token,  # type: ignore
            share_url=f"{base_url}/courses/shared/{share.share_token}",  # type: ignore
            is_public=share.is_public,  # type: ignore
            expires_at=share.expires_at,  # type: ignore
            created_at=share.created_at,  # type: ignore
            access_count=0  # Future: implement tracking
        ))
    
    return result


@router.delete("/{course_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_share_link(
    course_id: int,
    share_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete/revoke a share link (owner only).
    
    Important: Deleting a share link does NOT remove enrollments.
    Users who already enrolled will retain access.
    
    This is intentional design:
    - Prevents disruption for users already learning
    - Owner can still remove individual users via enrollment management (future feature)
    
    Args:
        course_id: ID of the course
        share_id: ID of the share link to delete
        db: Database session
        current_user: Authenticated user (must be course owner)
        
    Raises:
        404: Share link not found
        403: User is not the course owner
    """
    # Verify ownership: Only owner can delete share links
    course = require_course_ownership(course_id, current_user, db)
    
    # Get share
    share = db.query(CourseShare).filter(
        CourseShare.id == share_id,
        CourseShare.course_id == course_id
    ).first()
    
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    
    # Delete
    db.delete(share)
    db.commit()
    
    logger.info(f"User {current_user.id} deleted share link {share_id} for course {course_id}")

@router.delete("/{course_id}/enrollments/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_enrollment(
    course_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Revoke a user's enrollment (owner only).
    
    Use case: Remove users who enrolled via public link
    before you changed it to private.
    """
    course = require_course_ownership(course_id, current_user, db)
    
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.user_id == user_id
    ).first()
    
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    
    db.delete(enrollment)
    db.commit()
    
    logger.info(f"User {current_user.id} revoked enrollment for user {user_id} in course {course_id}")