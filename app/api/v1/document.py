import logging
import os
from typing import Any, List
from fastapi import APIRouter, Depends, status, BackgroundTasks
from fastapi import UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import io
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import json
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.dependencies import get_current_active_user
from app.db.base import get_db, SessionLocal
from app.models.user import User
from app.models.document import Document
from app.schemas.document import Document as DocumentSchema
from app.core.document_processor import DocumentProcessor
from app.services.file_service import FileService
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

class TaskQueue:
    """Google Cloud Tasks helper."""
    
    def __init__(self):
        self.is_local = os.getenv('ENV', 'local') == 'local'
        if not self.is_local:
            self.client = tasks_v2.CloudTasksClient()
            self.project = settings.GCS_PROJECT_ID
            self.location = 'asia-southeast1'
            self.queue = 'document-processing'
        
    def enqueue_document_processing(
        self,
        document_id: int,
        file_path: str,
        filename: str,
        user_id: int,
        delay_seconds: int = 0
    ):
        """Enqueue a document processing task."""
        
        # For local development, process synchronously
        if self.is_local:
            logger.info(f"LOCAL ENV: Processing document {document_id} synchronously")
            from app.db.base import SessionLocal
            db = SessionLocal()
            try:
                processor = DocumentProcessor(db)
                processor.process_and_store(
                    file_path=file_path,
                    filename=filename,
                    document_id=document_id,
                    user_id=user_id
                )
            finally:
                db.close()
            return "local-sync-processing"
        
        # For cloud, use Cloud Tasks
        parent = self.client.queue_path(self.project, self.location, self.queue)
        
        # Construct the request body
        payload = {
            'document_id': document_id,
            'file_path': file_path,
            'filename': filename,
            'user_id': user_id
        }
        
        # Construct the task
        task = {
            'http_request': {
                'http_method': tasks_v2.HttpMethod.POST,
                'url': f'{settings.BACKEND_URL}/api/v1/document/internal/process-document',
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
            task['schedule_time'] = timestamp # type: ignore
        
        # Create the task
        response = self.client.create_task(
            request={'parent': parent, 'task': task}
        )
        
        logger.info(f'Created task {response.name} for document {document_id}')
        return response.name

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

@router.post("/upload", response_model=DocumentSchema, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Upload document and queue for processing.
    """
    filename = getattr(file, "filename", "") or ""
    if not filename.lower().endswith(('.pdf', '.docx', '.txt')):
        raise HTTPException(status_code=400, detail="Unsupported file type.")
    
    try:
        # Upload to GCS
        dcs_file_service = FileService()
        file_info = await dcs_file_service.upload_file(
            file, 
            user_id=current_user.id, # type: ignore
            metadata={"user_email": current_user.email}
        )
        
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
        # Create document record with "queued" status
        document = Document(
            title=file_info["filename"],
            filename=file_info["filename"],
            file_path=file_info["gcs_path"],
            file_type=file_info["content_type"],
            file_size=file_info["file_size"],
            status="queued",
            extracted_text=extracted_text,
            owner_id=current_user.id,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # Queue processing task with Cloud Tasks
        try:
            task_queue = TaskQueue()
            task_queue.enqueue_document_processing(
                document_id=document.id,  # type: ignore
                file_path=file_info["gcs_path"],
                filename=file_info["filename"],
                user_id=current_user.id  # type: ignore
            )
            logger.info(f"Document ID '{document.id}' queued for processing")
        except Exception as e:
            logger.error(f"Failed to queue task: {e}")
            document.status = "failed"  # type: ignore
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to queue processing task: {str(e)}")
        
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
    Possible statuses: queued, processing, processed, failed
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
    
@router.get("/view-document", response_model=List[DocumentSchema])
def get_document_by_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get all documents for the current user.
    """
    documents = db.query(Document).filter(Document.owner_id == current_user.id).all()
    return documents

class ProcessDocumentRequest(BaseModel):
    document_id: int
    file_path: str
    filename: str
    user_id: int

@router.post("/internal/process-document")
async def process_document_internal(
    request: ProcessDocumentRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Internal endpoint called by Cloud Tasks to process documents.
    This endpoint should be protected in production.
    """
    try:
        logger.info(f"Processing document {request.document_id} from Cloud Tasks")
        
        # Update status to processing
        doc = db.query(Document).filter(Document.id == request.document_id).first()
        if doc:
            doc.status = "processing" # type: ignore
            db.commit()
        
        # Process document
        processor = DocumentProcessor(db)
        processor.process_and_store(
            file_path=request.file_path,
            filename=request.filename,
            document_id=request.document_id,
            user_id=request.user_id
        )
        
        logger.info(f"Successfully processed document {request.document_id}")
        return {"status": "success", "document_id": request.document_id}
        
    except Exception as e:
        logger.error(f"Processing failed for document {request.document_id}: {e}")
        
        # Update status to failed
        try:
            doc = db.query(Document).filter(Document.id == request.document_id).first()
            if doc:
                doc.status = "failed" # type: ignore
                db.commit()
        except:
            pass
            
        raise HTTPException(status_code=500, detail=str(e))