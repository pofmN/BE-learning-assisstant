"""
Conversation API endpoints for Q&A chat functionality.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.user import User
from app.models.conversation import Conversation, ConversationMessage, ConversationSummary
from app.models.document import Document
from app.core.agents.chat.qa_chat import QAChatAgent
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# Schemas
class ConversationCreateRequest(BaseModel):
    """Request to create a new conversation."""
    document_ids: Optional[List[int]] = Field(
        None, 
        description="Optional list of document IDs to search. If None, searches all user's documents."
    )


class ConversationResponse(BaseModel):
    """Conversation response."""
    id: int
    title: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    message_count: int

    class Config:
        from_attributes = True


class MessageRequest(BaseModel):
    """Request to send a message."""
    message: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    """Response from the Q&A agent."""
    conversation_id: int
    user_message: str
    assistant_response: str
    intent: Optional[str]  # "normal_chat" or "document_query"
    source_chunks: List[int] = Field(default_factory=list)
    timestamp: datetime


class ConversationMessageSchema(BaseModel):
    """Message in conversation history."""
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationHistoryResponse(BaseModel):
    """Full conversation history."""
    conversation: ConversationResponse
    messages: List[ConversationMessageSchema]
    summaries: List[str] = Field(
        default_factory=list,
        description="Summaries of previous conversation segments"
    )


# Endpoints
@router.post("/create", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Create a new conversation.

    A conversation is a persistent chat session where users can ask questions
    about their documents or have general discussions.
    """
    try:
        # Validate document access if document_ids provided
        if request.document_ids:
            documents = db.query(Document).filter(
                Document.id.in_(request.document_ids),
                Document.owner_id == current_user.id
            ).all()
            
            if len(documents) != len(request.document_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to one or more of the specified documents"
                )
        
        # Create conversation
        conversation = Conversation(
            user_id=current_user.id,
            title="New Conversation",  # Will be updated with first question
            created_at=datetime.now(timezone.utc)
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        logger.info(f"Created conversation {conversation.id} for user {current_user.id}")
        
        return ConversationResponse(
            id=int(conversation.id),  # type: ignore
            title=str(conversation.title) if conversation.title else None,  # type: ignore
            created_at=conversation.created_at,  # type: ignore
            updated_at=conversation.updated_at,  # type: ignore
            message_count=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation"
        )


@router.post("/send/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: int,
    document_ids: List[int],
    request: MessageRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Send a message to a conversation and get AI response.

    The agent will:
    1. Classify intent (normal chat vs document query)
    2. For document queries: retrieve relevant chunks and generate answer
    3. For normal chat: have a friendly conversation
    4. Automatically summarize every 5 Q&A pairs for memory
    """
    try:
        # Verify conversation exists and belongs to user
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get user's document IDs
        # documents = db.query(Document).filter(
        #     Document.owner_id == current_user.id
        # ).all()
        # document_ids = [int(doc.id) for doc in documents]  # type: ignore
        
        # Process message through Q&A agent
        agent = QAChatAgent(db)
        result = agent.process_message(
            conversation_id=conversation_id,
            user_id=int(current_user.id),  # type: ignore
            message=request.message,
            document_ids=document_ids if document_ids else None
        )
        
        # Update conversation title from first message if needed
        if str(conversation.title) == "New Conversation":  # type: ignore
            # Use first few words of message as title
            title_words = request.message.split()[:8]
            new_title = " ".join(title_words)
            if len(request.message.split()) > 8:
                new_title += "..."
            conversation.title = new_title  # type: ignore
            db.commit()
        
        return MessageResponse(
            conversation_id=conversation_id,
            user_message=request.message,
            assistant_response=result["response"],
            intent=result.get("intent"),
            source_chunks=result.get("source_chunks", []),
            timestamp=datetime.now(timezone.utc)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


@router.get("/history/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get full conversation history with messages and summaries.

    Args:
        conversation_id: Conversation ID
        limit: Maximum number of recent messages to return (default: 50)
    """
    try:
        # Verify conversation exists and belongs to user
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get recent messages
        messages = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(
            ConversationMessage.created_at.desc()
        ).limit(limit).all()
        
        # Reverse to chronological order
        messages = list(reversed(messages))
        
        # Get summaries
        summaries = db.query(ConversationSummary).filter(
            ConversationSummary.conversation_id == conversation_id
        ).order_by(
            ConversationSummary.created_at
        ).all()
        
        # Count total messages
        message_count = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).count()
        
        return ConversationHistoryResponse(
            conversation=ConversationResponse(
                id=int(conversation.id),  # type: ignore
                title=str(conversation.title) if conversation.title else None,  # type: ignore
                created_at=conversation.created_at,  # type: ignore
                updated_at=conversation.updated_at,  # type: ignore
                message_count=message_count
            ),
            messages=[ConversationMessageSchema.from_orm(msg) for msg in messages],
            summaries=[str(summary.summary) for summary in summaries]  # type: ignore
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation history"
        )


@router.get("/list", response_model=List[ConversationResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    List all conversations for the current user.

    Args:
        skip: Number of conversations to skip (for pagination)
        limit: Maximum number of conversations to return
    """
    try:
        conversations = db.query(Conversation).filter(
            Conversation.user_id == current_user.id
        ).order_by(
            Conversation.updated_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Add message count to each conversation
        result = []
        for conv in conversations:
            message_count = db.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == conv.id
            ).count()
            
            result.append(ConversationResponse(
                id=int(conv.id),  # type: ignore
                title=str(conv.title) if conv.title else None,  # type: ignore
                created_at=conv.created_at,  # type: ignore
                updated_at=conv.updated_at,  # type: ignore
                message_count=message_count
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversations"
        )


@router.delete("/delete/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Delete a conversation and all its messages.

    This action cannot be undone.
    """
    try:
        # Verify conversation exists and belongs to user
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Delete conversation (cascade will delete messages and summaries)
        db.delete(conversation)
        db.commit()
        
        logger.info(f"Deleted conversation {conversation_id} for user {current_user.id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )
