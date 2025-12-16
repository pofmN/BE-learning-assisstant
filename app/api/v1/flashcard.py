"""
API endpoints for flashcard interactions - study sessions, spaced repetition, etc.
"""
from typing import List, Optional, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.user import User
from app.models.course import Course, FlashCard
from app.models.quiz_attempt import FlashcardReview
from app.schemas.flashcard import FlashcardResponse, FlashcardReviewSubmit, FlashcardStudyInSectionResponse, FlashcardStudyInCourseResponse

router = APIRouter()

# ============= Flashcard Endpoints =============

@router.get("/courses/{course_id}", response_model=List[FlashcardResponse])
def get_course_flashcards(
    course_id: int,
    section_id: Optional[int] = None,
    due_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get flashcards for a course or section.
    
    Args:
        course_id: Course ID
        section_id: Optional section filter
        due_only: If True, only return cards due for review
    """
    # Verify course access
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Query flashcards
    query = db.query(FlashCard).filter(FlashCard.course_id == course_id)
    if section_id:
        query = query.filter(FlashCard.section_id == section_id)
    
    flashcards = query.all()
    if not flashcards:
        raise HTTPException(status_code=404, detail="No flashcards found for this course/section.")
    
    # Get review stats for each card
    result = []
    for card in flashcards:
        reviews = db.query(FlashcardReview).filter(
            FlashcardReview.flashcard_id == card.id,
            FlashcardReview.user_id == current_user.id 
        ).all()
        
        times_reviewed = len(reviews)
        avg_confidence = sum(r.confidence_level for r in reviews) / times_reviewed if times_reviewed > 0 else 0
        
        # Calculate next review date (spaced repetition)
        next_review = None
        if reviews:
            last_review = max(reviews, key=lambda r: r.created_at)
            next_review = last_review.next_review_date
        
        # Filter by due date if requested
        if due_only:
            if next_review is None or next_review <= datetime.now():  # type: ignore
                result.append(FlashcardResponse(
                    id=int(card.id),  # type: ignore
                    course_id=int(card.course_id),  # type: ignore
                    section_id=int(card.section_id) if card.section_id else None,  # type: ignore
                    question=str(card.question),  # type: ignore
                    answer=str(card.answer),  # type: ignore
                    times_reviewed=times_reviewed,
                    avg_confidence=float(avg_confidence),  # type: ignore
                    next_review=next_review  # type: ignore
                ))
        else:
            result.append(FlashcardResponse(
                id=int(card.id),  # type: ignore
                course_id=int(card.course_id),  # type: ignore
                section_id=int(card.section_id) if card.section_id else None,  # type: ignore
                question=str(card.question),  # type: ignore
                answer=str(card.answer),  # type: ignore
                times_reviewed=times_reviewed,
                avg_confidence=float(avg_confidence),  # type: ignore
                next_review=next_review  # type: ignore
            ))
    
    return result


@router.get("/{flashcard_id}/content", response_model=FlashcardResponse)
def get_flashcard(
    flashcard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get a single flashcard with review stats."""
    card = db.query(FlashCard).filter(FlashCard.id == flashcard_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    
    # Get review stats
    reviews = db.query(FlashcardReview).filter(
        FlashcardReview.flashcard_id == flashcard_id,
        FlashcardReview.user_id == current_user.id 
    ).all()
    
    times_reviewed = len(reviews)
    avg_confidence = sum(r.confidence_level for r in reviews) / times_reviewed if times_reviewed > 0 else 0
    
    next_review = None
    if reviews:
        last_review = max(reviews, key=lambda r: r.created_at)
        next_review = last_review.next_review_date
    
    return FlashcardResponse(
        id=int(card.id),  # type: ignore
        course_id=int(card.course_id),  # type: ignore
        section_id=int(card.section_id) if card.section_id else None,  # type: ignore
        question=str(card.question),  # type: ignore
        answer=str(card.answer),  # type: ignore
        times_reviewed=times_reviewed,
        avg_confidence=float(avg_confidence),  # type: ignore
        next_review=next_review  # type: ignore
    )


@router.post("/{flashcard_id}/review", status_code=status.HTTP_201_CREATED)
def review_flashcard(
    review_data: FlashcardReviewSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Submit a flashcard review with confidence level.
    Uses spaced repetition algorithm to schedule next review.
    """
    # Verify flashcard exists
    card = db.query(FlashCard).filter(FlashCard.id == review_data.flashcard_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    
    # Calculate next review date based on confidence (spaced repetition)
    next_review_date = _calculate_next_review(review_data.confidence_level)
    
    # Create review record
    review = FlashcardReview(
        flashcard_id=review_data.flashcard_id,
        user_id=int(current_user.id),  # type: ignore
        confidence_level=review_data.confidence_level,
        time_spent=review_data.time_spent,
        next_review_date=next_review_date
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return {
        "review_id": review.id,
        "flashcard_id": review.flashcard_id,
        "confidence_level": review.confidence_level,
        "next_review_date": review.next_review_date,
        "message": "Flashcard reviewed successfully"
    }

@router.get("/sections/{section_id}/stats", response_model=FlashcardStudyInSectionResponse)
def get_flashcard_stats_by_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get flashcard study statistics for a section.
    """
    # Get all flashcards for section
    flashcards = db.query(FlashCard).filter(FlashCard.section_id == section_id).all()
    flashcard_ids = [f.id for f in flashcards]
    
    # Get user's reviews for these cards
    reviews = db.query(FlashcardReview).filter(
        FlashcardReview.flashcard_id.in_(flashcard_ids),
        FlashcardReview.user_id == current_user.id 
    ).all()
    
    cards_reviewed = len(set(r.flashcard_id for r in reviews))
    avg_confidence = sum(r.confidence_level for r in reviews) / len(reviews) if reviews else 0
    total_time = sum(r.time_spent for r in reviews if r.time_spent is not None) or 0  # type: ignore
    
    # Count cards due for review
    cards_due = 0
    for card in flashcards:
        card_reviews = [r for r in reviews if int(r.flashcard_id) == int(card.id)]  # type: ignore
        if not card_reviews:
            cards_due += 1
        else:
            last_review = max(card_reviews, key=lambda r: r.created_at)
            if last_review.next_review_date is None or last_review.next_review_date <= datetime.now(tz=last_review.next_review_date.tzinfo):  # type: ignore
                cards_due += 1
    
    return FlashcardStudyInSectionResponse(
        section_id=section_id,
        cards_reviewed=cards_reviewed,
        avg_confidence=float(avg_confidence),  # type: ignore
        total_time_seconds=int(total_time),  # type: ignore
        cards_to_review=cards_due
    )


@router.get("/courses/{course_id}/stats", response_model=FlashcardStudyInCourseResponse)
def get_flashcard_stats(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get flashcard study statistics for a course.
    """
    # Get all flashcards for course
    flashcards = db.query(FlashCard).filter(FlashCard.course_id == course_id).all()
    flashcard_ids = [f.id for f in flashcards]
    
    # Get user's reviews for these cards
    reviews = db.query(FlashcardReview).filter(
        FlashcardReview.flashcard_id.in_(flashcard_ids),
        FlashcardReview.user_id == current_user.id 
    ).all()
    
    cards_reviewed = len(set(r.flashcard_id for r in reviews))
    avg_confidence = sum(r.confidence_level for r in reviews) / len(reviews) if reviews else 0
    total_time = sum(r.time_spent for r in reviews if r.time_spent is not None) or 0  # type: ignore
    
    # Count cards due for review
    cards_due = 0
    for card in flashcards:
        card_reviews = [r for r in reviews if int(r.flashcard_id) == int(card.id)]  # type: ignore
        if not card_reviews:
            cards_due += 1
        else:
            last_review = max(card_reviews, key=lambda r: r.created_at)
            if last_review.next_review_date is None or last_review.next_review_date <= datetime.now(tz=last_review.next_review_date.tzinfo):  # type: ignore
                cards_due += 1
    
    return FlashcardStudyInCourseResponse(
        course_id=course_id,
        cards_reviewed=cards_reviewed,
        avg_confidence=float(avg_confidence),  # type: ignore
        total_time_seconds=int(total_time),  # type: ignore
        cards_to_review=cards_due
    )

@router.get("/courses/{course_id}/due", response_model=List[FlashcardResponse])
def get_due_flashcards(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get all due flashcards for review in a course.
    """
    flashcards = db.query(FlashCard).filter(FlashCard.course_id == course_id).all()
    flashcard_ids = [f.id for f in flashcards]
    reviews = db.query(FlashcardReview).filter(
        FlashcardReview.flashcard_id.in_(flashcard_ids),
        FlashcardReview.user_id == current_user.id
    ).all()

    due_flashcards = []
    for card in flashcards:
        card_reviews = [r for r in reviews if int(r.flashcard_id) == int(card.id)]  # type: ignore
        if not card_reviews:
            continue
        times_reviewed = len(card_reviews)
        avg_confidence = sum(r.confidence_level for r in card_reviews) / times_reviewed if times_reviewed > 0 else 0
        last_review = max(card_reviews, key=lambda r: r.created_at)
        next_review = last_review.next_review_date
        # Only include if next_review is due
        if next_review is not None and next_review <= datetime.now(tz=next_review.tzinfo): # type: ignore
            due_flashcards.append(FlashcardResponse(
                id=int(card.id),  # type: ignore
                course_id=int(card.course_id),  # type: ignore
                section_id=int(card.section_id) if card.section_id else None, # type: ignore
                question=str(card.question),
                answer=str(card.answer),
                times_reviewed=times_reviewed,
                avg_confidence=float(avg_confidence), # type: ignore
                next_review=next_review  # type: ignore
            ))
    return due_flashcards

@router.get("/sections/{section_id}/due", response_model=List[FlashcardResponse])
def count_due_flashcards_in_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Count flashcards due for review in a section.
    """
    # Get all flashcards for section
    flashcards = db.query(FlashCard).filter(FlashCard.section_id == section_id).all()
    flashcard_ids = [f.id for f in flashcards]
    
    # Get user's reviews for these cards
    reviews = db.query(FlashcardReview).filter(
        FlashcardReview.flashcard_id.in_(flashcard_ids),
        FlashcardReview.user_id == current_user.id 
    ).all()
    
    # Count cards due for review
    due_flashcard = []
    for card in flashcards:
        card_reviews = [r for r in reviews if int(r.flashcard_id) == int(card.id)]  # type: ignore
        if not card_reviews:
            continue
        times_reviewed = len(card_reviews)
        avg_confidence = sum(r.confidence_level for r in card_reviews) / times_reviewed if times_reviewed > 0 else 0
        last_review = max(card_reviews, key=lambda r: r.created_at)
        next_review = last_review.next_review_date
        # Only include if next_review is due
        if next_review is not None and next_review <= datetime.now(tz=next_review.tzinfo): # type: ignore
            due_flashcard.append(FlashcardResponse(
                id=int(card.id),  # type: ignore
                course_id=int(card.course_id),  # type: ignore
                section_id=int(card.section_id) if card.section_id else None, # type: ignore
                question=str(card.question),
                answer=str(card.answer),
                times_reviewed=times_reviewed,
                avg_confidence=float(avg_confidence), # type: ignore
                next_review=next_review  # type: ignore
            ))
    return due_flashcard

# ============= Helper Functions =============

def _calculate_next_review(confidence_level: int) -> datetime:
    """
    Calculate next review date using spaced repetition algorithm.
    
    Confidence levels:
    1 - Review in 1 hour
    2 - Review in 1 day
    3 - Review in 3 days
    4 - Review in 1 week
    5 - Review in 2 weeks
    """
    intervals = {
        1: timedelta(hours=1),
        2: timedelta(days=1),
        3: timedelta(days=3),
        4: timedelta(weeks=1),
        5: timedelta(weeks=2)
    }
    
    interval = intervals.get(confidence_level, timedelta(days=1))
    return datetime.now() + interval
