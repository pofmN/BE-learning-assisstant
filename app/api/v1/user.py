from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.schemas.user import UserInDB
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()



@router.get("/view-profile", response_model=UserInDB, status_code=status.HTTP_200_OK)
def view_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to view the profile of the currently authenticated user.
    
    Args:
        current_user: The currently authenticated user (injected by dependency)
        db: Database session (injected by dependency)
        
    Returns:
        UserInDB: The profile information of the current user
    """
    try:
        return current_user
    except Exception as e:
        logger.error(f"Error retrieving user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user profile"
        )