"""
Document management endpoints.
"""
import os
from typing import Any, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import Document as DocumentSchema, DocumentWithText
from app.utils.document_parser import extract_text_from_document
from app.utils.file_upload import save_upload_file

router = APIRouter()


@router.post("/upload", response_model=DocumentSchema, status_code=status.HTTP_201_CREATED)
async def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Upload and parse a document (PDF, DOCX, or PPTX).

    Args:
        title: Document title
        file: Uploaded file
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created document

    Raises:
        HTTPException: If file upload or parsing fails
    """
    try:
        # Save file
        file_path, filename, file_size = await save_upload_file(file)

        # Get file type
        file_type = filename.rsplit(".", 1)[1].lower()

        # Extract text from document
        try:
            extracted_text = extract_text_from_document(file_path, file_type)
        except Exception as e:
            # Clean up file on parsing error
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error parsing document: {str(e)}",
            )

        # Create document record
        document = Document(
            title=title,
            filename=filename,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            extracted_text=extracted_text,
            owner_id=current_user.id,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading document: {str(e)}",
        )


@router.get("", response_model=List[DocumentSchema])
def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get list of user's documents.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of documents
    """
    documents = (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return documents


@router.get("/{document_id}", response_model=DocumentWithText)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get document by ID with full text.

    Args:
        document_id: Document ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Document details

    Raises:
        HTTPException: If document not found or access denied
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.owner_id != current_user.id: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete document by ID.

    Args:
        document_id: Document ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If document not found or access denied
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.owner_id != current_user.id: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Delete file from disk
    if os.path.exists(document.file_path): # type: ignore
        os.remove(document.file_path) # type: ignore

    # Delete database record
    db.delete(document)
    db.commit()
