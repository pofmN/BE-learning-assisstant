
import logging
from typing import Any
from fastapi import APIRouter, Depends, status
from fastapi import UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import io

from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.user import User
from app.models.document import Document
from app.schemas.document import Document as DocumentSchema
from app.services.file_service import FileService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload", response_model=DocumentSchema, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    ) -> Any:
    """
    Endpoint to upload a document for processing.
    """
    filename = getattr(file, "filename", "") or ""
    if not filename.lower().endswith(('.pdf', '.docx', '.txt')):
        raise HTTPException(status_code=400, detail="Unsupported file type.")
    
    try:
        dcs_file_service = FileService()
        file_info = await dcs_file_service.upload_file(file, user_id=current_user.id, metadata={"user_email": current_user.email})  # type: ignore
        
        extracted_text = None
        if filename.lower().endswith('.txt'):
            file.file.seek(0)
            try:
                extracted_text = file.file.read().decode('utf-8', errors='ignore')
            except Exception as e:
                logger.error(f"Error reading text file: {e}")
                extracted_text = None
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload document.")
    document = Document(
        title=file_info["filename"],
        filename=file_info["filename"],
        file_path=file_info["gcs_path"],
        file_type=file_info["content_type"],
        file_size=file_info["file_size"],
        extracted_text=extracted_text,
        owner_id=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    logger.info(f"Document '{filename}' uploaded successfully by user '{current_user.email}'.")
    
    return document
    
@router.get("/{document_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> None:
    """
    Delete a document.
    """
    document = db.query(Document).filter(Document.id == document_id, Document.owner_id==current_user.id).first()
    print("here is document")
    print(document)
    if not document: 
        raise HTTPException(status_code=404, detail="Document not found")
    
    try: 
        gcs_file_service = FileService()
        gcs_file_service.delete_file(document.file_path) # type: ignore

        db.delete(document)
        db.commit()

        logger.info(f"Document ID '{document_id}' deleted successfully by user '{current_user.email}'.")
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        db.rollback
        raise HTTPException(status_code=500, detail="Failed to delete document.")