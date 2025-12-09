
import logging
from typing import Any
from fastapi import APIRouter, Depends, status, BackgroundTasks
from fastapi import UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import io

from app.core.dependencies import get_current_active_user
from app.db.base import get_db, SessionLocal
from app.models.user import User
from app.models.document import Document
from app.schemas.document import Document as DocumentSchema
from app.core.document_processor import DocumentProcessor
from app.services.file_service import FileService

logger = logging.getLogger(__name__)

router = APIRouter()

def process_document_background(
    file_path: str,
    filename: str,
    document_id: int,
    user_id: int,
):
    """
    Background task to process a document.
    """
    db = SessionLocal()  # Create a new session for the background task
    try:
        logger.info(f"Starting background processing for document ID {document_id}")
        processor = DocumentProcessor(db)
        processor.process_and_store(
            file_path=file_path,
            filename=filename,
            document_id=document_id,
            user_id=user_id
        )
        logger.info(f"Completed background processing for document ID {document_id}")
    except Exception as e:
        logger.error(f"Error processing document ID {document_id} in background: {e}")
    finally:
        db.close()

@router.post("/upload", response_model=DocumentSchema, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
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
    try:
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
        background_tasks.add_task(
            process_document_background,
            file_path=file_info["gcs_path"],
            filename=file_info["filename"],
            document_id=document.id, #type: ignore
            user_id=current_user.id, #type: ignore
        )
        logger.info(f"Document ID '{document.id}' queued for processing by user '{current_user.email}'.")
        
        logger.info(f"Document '{filename}' uploaded successfully by user '{current_user.email}'.")
        
        return document
    except Exception as e:
        logger.error(f"Error processing document to database: {e}")
        raise HTTPException(status_code=500, detail="Failed to save document metadata.")
    
@router.get("/{document_id}/status")
async def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get the processing status of a document.
    """
    document = db.query(Document).filter(Document.id == document_id, Document.owner_id==current_user.id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"document_id": document.id, "status": getattr(document, "status", "unknown")}  # type: ignore


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