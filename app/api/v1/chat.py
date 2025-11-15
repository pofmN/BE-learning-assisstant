"""
Virtual teacher chat WebSocket endpoint.
"""
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.user import User
from app.models.document import Document
from app.services.ai_service import ai_service

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """
        Accept and store WebSocket connection.

        Args:
            websocket: WebSocket connection
            user_id: User ID
        """
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        """
        Remove WebSocket connection.

        Args:
            user_id: User ID
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_message(self, message: str, user_id: int):
        """
        Send message to user.

        Args:
            message: Message to send
            user_id: User ID
        """
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)


manager = ConnectionManager()


@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    document_id: Optional[int] = Query(None),
):
    """
    WebSocket endpoint for virtual teacher chat.

    Args:
        websocket: WebSocket connection
        token: JWT token for authentication
        document_id: Optional document ID for context

    Note:
        In production, implement proper JWT token validation here.
        For now, this is a simplified implementation.
    """
    # TODO: Implement proper JWT token validation
    # For demonstration, we'll accept any connection
    user_id = 1  # Mock user ID

    await manager.connect(websocket, user_id)

    try:
        # Get document context if provided
        context = None
        if document_id:
            # TODO: Get document from database using proper dependency injection
            # For now, using mock context
            context = f"Document ID: {document_id}"

        # Send welcome message
        await manager.send_message(
            json.dumps(
                {
                    "type": "system",
                    "message": "Welcome! I'm your virtual teacher. How can I help you today?",
                }
            ),
            user_id,
        )

        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")

            if not user_message:
                continue

            # Echo user message
            await manager.send_message(
                json.dumps({"type": "user", "message": user_message}), user_id
            )

            # Get AI response
            try:
                ai_response = await ai_service.chat(user_message, context)

                # Send AI response
                await manager.send_message(
                    json.dumps({"type": "assistant", "message": ai_response}), user_id
                )

            except Exception as e:
                await manager.send_message(
                    json.dumps(
                        {
                            "type": "error",
                            "message": f"Error generating response: {str(e)}",
                        }
                    ),
                    user_id,
                )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        manager.disconnect(user_id)
        print(f"WebSocket error: {str(e)}")
