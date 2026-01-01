from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
from datetime import datetime
from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.schemas.user import UserInDB, UserPersonalityInDB
from app.models.user import User
from app.models.user_personality import UserPersonality

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
        user_info = db.query(User).filter(User.id == current_user.id).first()
        user_profile = UserInDB(
            id=user_info.id, #type: ignore
            email=user_info.email,#type: ignore
            username=user_info.username,#type: ignore
            full_name=user_info.full_name,#type: ignore
            role=user_info.role if user_info.role is not None else "student", #type: ignore
            is_active=user_info.is_active,#type: ignore
            avatar_url=user_info.avatar_url,#type: ignore
            created_at=user_info.created_at,#type: ignore
            updated_at=user_info.updated_at#type: ignore
        )
        return user_profile
    except Exception as e:
        logger.error(f"Error retrieving user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user profile"
        )
    
@router.post("/update-profile", response_model=UserInDB, status_code=status.HTTP_200_OK)
def update_profile(
    updated_user: UserInDB,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to update the profile of the currently authenticated user.
    
    Args:
        updated_user: The updated user information
        updated_at: Can be empty, will be set to current time
        
    Returns:
        UserInDB: The updated profile information of the current user
    """
    try:
        user_record = db.query(User).filter(User.id == current_user.id).first()
        if not user_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update fields
        user_record.email = updated_user.email #type: ignore
        user_record.username = updated_user.username #type: ignore
        user_record.full_name = updated_user.full_name #type: ignore
        user_record.role = updated_user.role #type: ignore
        user_record.avatar_url = updated_user.avatar_url #type: ignore
        
        db.commit()
        db.refresh(user_record)
        
        return UserInDB(
            id=user_record.id, #type: ignore
            email=user_record.email,#type: ignore
            username=user_record.username,#type: ignore
            full_name=user_record.full_name,#type: ignore
            role=user_record.role,#type: ignore
            is_active=user_record.is_active,#type: ignore
            avatar_url=user_record.avatar_url,#type: ignore
            created_at=user_record.created_at,#type: ignore
            updated_at=datetime.now()#type: ignore
        )
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update user profile"
        )

@router.get("/user-personality", response_model=UserPersonalityInDB, status_code=status.HTTP_200_OK)
def get_user_personality(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to get the personality profile of the currently authenticated user.
    
    Args:
        current_user: The currently authenticated user (injected by dependency)
        db: Database session (injected by dependency)
        
    Returns:
        UserPersonalityInDB: The personality profile information of the current user
    """
    personality_info = db.query(UserPersonality).filter(UserPersonality.user_id == current_user.id).first()
    if not personality_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personality profile not found"
        )
    return personality_info

@router.post("/update-user-personality", response_model=UserPersonalityInDB, status_code=status.HTTP_200_OK)
def update_user_personality(
    updated_personality: UserPersonalityInDB,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to update the personality profile of the currently authenticated user.
    
    Args:
        updated_personality: The updated personality information
        current_user: The currently authenticated user (injected by dependency)
        db: Database session (injected by dependency)
        
    Returns:
        UserPersonalityInDB: The updated personality profile information of the current user
    """
    try:
        personality_record = db.query(UserPersonality).filter(UserPersonality.user_id == current_user.id).first()
        if not personality_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personality profile not found"
            )
        
        # Update fields
        personality_record.date_of_birth = updated_personality.date_of_birth #type: ignore
        
        db.commit()
        db.refresh(personality_record)
        
        return personality_record
    except Exception as e:
        logger.error(f"Error updating user personality profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update user personality profile"
        )