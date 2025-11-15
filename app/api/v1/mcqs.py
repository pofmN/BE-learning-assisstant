"""
MCQ generation endpoints.
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.models.document import Document
from app.models.mcq import MCQ
from app.models.user import User
from app.schemas.mcq import MCQ as MCQSchema, MCQGenerate, MCQGenerateResponse
from app.services.ai_service import ai_service

router = APIRouter()


@router.post("/generate", response_model=MCQGenerateResponse)
async def generate_mcqs(
    request: MCQGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate MCQs from a document.

    Args:
        request: MCQ generation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Generated MCQs

    Raises:
        HTTPException: If document not found or access denied
    """
    # Get document
    document = db.query(Document).filter(Document.id == request.document_id).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    if not document.extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted text",
        )

    # Generate MCQs using AI service
    try:
        generated_mcqs = await ai_service.generate_mcqs(
            text=document.extracted_text,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            topic=request.topic,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating MCQs: {str(e)}",
        )

    # Save MCQs to database
    mcq_objects = []
    for mcq_data in generated_mcqs:
        mcq = MCQ(
            document_id=document.id,
            question=mcq_data["question"],
            choices=mcq_data["choices"],
            correct_answer=mcq_data["correct_answer"],
            explanation=mcq_data.get("explanation"),
            difficulty=mcq_data.get("difficulty", "medium"),
            topic=mcq_data.get("topic"),
        )
        db.add(mcq)
        mcq_objects.append(mcq)

    db.commit()
    for mcq in mcq_objects:
        db.refresh(mcq)

    return {
        "mcqs": mcq_objects,
        "message": f"Successfully generated {len(mcq_objects)} MCQs",
    }


@router.get("", response_model=List[MCQSchema])
def list_mcqs(
    document_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get list of MCQs, optionally filtered by document.

    Args:
        document_id: Optional document ID to filter by
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of MCQs
    """
    query = db.query(MCQ).join(Document).filter(Document.owner_id == current_user.id)

    if document_id:
        query = query.filter(MCQ.document_id == document_id)

    mcqs = query.offset(skip).limit(limit).all()
    return mcqs


@router.get("/{mcq_id}", response_model=MCQSchema)
def get_mcq(
    mcq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get MCQ by ID.

    Args:
        mcq_id: MCQ ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        MCQ details

    Raises:
        HTTPException: If MCQ not found or access denied
    """
    mcq = db.query(MCQ).filter(MCQ.id == mcq_id).first()

    if not mcq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ not found",
        )

    # Check if user owns the document
    if mcq.document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    return mcq
