"""
Q&A Chat Agent with routing for normal chat vs document-based RAG.
"""
import logging
import json
from typing import List, Dict, Any, Optional, TypedDict, Literal
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.conversation import Conversation, ConversationMessage, ConversationSummary
from app.core.llm_config import LLMFactory
from app.core.helpers.retriever import DocumentRetriever
from app.core.agents.chat.prompt import (
    INTENT_CLASSIFICATION_SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_USER_PROMPT_TEMPLATE,
    NORMAL_CHAT_SYSTEM_PROMPT,
    RAG_ANSWER_SYSTEM_PROMPT,
    RAG_ANSWER_USER_PROMPT_TEMPLATE,
    SUMMARIZATION_SYSTEM_PROMPT,
    SUMMARIZATION_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class IntentClassification(BaseModel):
    """Schema for intent classification."""
    intent: Literal["normal_chat", "document_query"]


class ConversationSummarySchema(BaseModel):
    """Schema for conversation summary."""
    summary: str


class QAChatState(TypedDict):
    """State for Q&A chat agent."""
    conversation_id: int
    user_id: int
    user_message: str
    document_ids: Optional[List[int]]  # Documents user has access to
    
    # Intent routing
    intent: Optional[str]  # "normal_chat" or "document_query"
    
    # RAG components
    retrieved_chunks: Optional[List[Dict[str, Any]]]
    context: Optional[str]
    
    # Conversation history
    conversation_history: List[Dict[str, str]]  # [{role, content}, ...]
    
    # Response
    assistant_response: Optional[str]
    source_chunk_ids: Optional[List[int]]
    
    # Metadata
    tokens_used: Optional[int]
    model_used: Optional[str]
    
    # Status
    status: str
    error: Optional[str]


class QAChatAgent:
    """
    Agent for handling Q&A conversations with routing between normal chat and RAG.
    """

    def __init__(self, db: Session):
        self.db = db
        
        # Different LLMs for different purposes
        self.classification_llm = LLMFactory.create_llm(
            temperature=0.0, 
            json_mode=True
        ).with_structured_output(IntentClassification)
        
        self.chat_llm = LLMFactory.create_llm(temperature=0.7)
        self.rag_llm = LLMFactory.create_llm(temperature=0.3)  # Lower temp for factual answers
        
        self.summary_llm = LLMFactory.create_llm(
            temperature=0.5,
            json_mode=True
        ).with_structured_output(ConversationSummarySchema)
        
        self.retriever = DocumentRetriever(db)
        self.graph = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(QAChatState)

        # Add nodes
        workflow.add_node("load_conversation_history", self._load_conversation_history)
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("normal_chat", self._normal_chat)
        workflow.add_node("retrieve_chunks", self._retrieve_chunks)
        workflow.add_node("generate_rag_answer", self._generate_rag_answer)
        workflow.add_node("save_message", self._save_message)
        workflow.add_node("check_summarization", self._check_summarization)

        # Define routing logic
        workflow.set_entry_point("load_conversation_history")
        workflow.add_edge("load_conversation_history", "classify_intent")
        
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_intent,
            {
                "normal_chat": "normal_chat",
                "document_query": "retrieve_chunks",
            }
        )
        
        workflow.add_edge("normal_chat", "save_message")
        workflow.add_edge("retrieve_chunks", "generate_rag_answer")
        workflow.add_edge("generate_rag_answer", "save_message")
        workflow.add_edge("save_message", "check_summarization")
        workflow.add_edge("check_summarization", END)

        return workflow.compile()

    def _load_conversation_history(self, state: QAChatState) -> QAChatState:
        """Load recent conversation history (last 10 messages + latest summary)."""
        try:
            conversation_id = state["conversation_id"]
            
            # Get last 10 messages for immediate context
            messages = self.db.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == conversation_id
            ).order_by(
                ConversationMessage.created_at.desc()
            ).limit(10).all()
            
            # Reverse to chronological order
            messages = list(reversed(messages))
            
            # Format conversation history
            history = []
            for msg in messages:
                history.append({
                    "role": str(msg.role),  # type: ignore
                    "content": str(msg.content),  # type: ignore
                })
            
            # Get latest summary for older context (if exists)
            latest_summary = self.db.query(ConversationSummary).filter(
                ConversationSummary.conversation_id == conversation_id
            ).order_by(ConversationSummary.created_at.desc()).first()
            
            if latest_summary:
                # Insert summary at the beginning as compressed history
                history.insert(0, {
                    "role": "system",
                    "content": f"[Previous conversation summary]: {str(latest_summary.summary)}"  # type: ignore
                })
            
            logger.info(f"Loaded {len(history)} messages (summary: {latest_summary is not None}) from conversation {conversation_id}")
            
            return {
                **state,
                "conversation_history": history,
                "status": "history_loaded"
            }
            
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            return {**state, "error": str(e), "status": "error"}

    def _classify_intent(self, state: QAChatState) -> QAChatState:
        """Classify user intent: normal chat vs document query."""
        try:
            user_message = state["user_message"]
            
            # Prepare prompt
            messages = [
                SystemMessage(content=INTENT_CLASSIFICATION_SYSTEM_PROMPT),
                HumanMessage(content=INTENT_CLASSIFICATION_USER_PROMPT_TEMPLATE.format(
                    message=user_message
                ))
            ]
            
            # Get classification
            result = self.classification_llm.invoke(messages)
            intent = result.intent if hasattr(result, 'intent') else result.get('intent', 'document_query')  # type: ignore
            
            logger.info(f"Classified intent: {intent}")
            
            return {
                **state,
                "intent": intent,
                "status": "intent_classified"
            }
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            # Default to document query on error
            return {**state, "intent": "document_query", "status": "intent_classified"}

    def _route_by_intent(self, state: QAChatState) -> str:
        """Route to appropriate node based on intent."""
        intent = state.get("intent", "document_query")
        return str(intent)

    def _normal_chat(self, state: QAChatState) -> QAChatState:
        """Handle normal conversation (non-document queries)."""
        try:
            user_message = state["user_message"]
            history = state.get("conversation_history", [])
            
            # Build messages with history
            messages: list = [SystemMessage(content=NORMAL_CHAT_SYSTEM_PROMPT)]  # type: ignore
            
            # Add conversation history (includes summary if present)
            for msg in history:
                if msg["role"] == "system":
                    # This is the summary - add as system context
                    messages.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))
            
            # Add current message
            messages.append(HumanMessage(content=user_message))
            
            # Generate response
            response = self.chat_llm.invoke(messages)
            
            return {
                **state,
                "assistant_response": str(response.content),  # type: ignore
                "model_used": "gpt-4o-mini",
                "status": "response_generated"
            }
            
        except Exception as e:
            logger.error(f"Error in normal chat: {e}")
            return {**state, "error": str(e), "status": "error"}

    def _retrieve_chunks(self, state: QAChatState) -> QAChatState:
        """Retrieve relevant document chunks for RAG."""
        try:
            user_message = state["user_message"]
            document_ids = state.get("document_ids")
            
            # Retrieve relevant chunks
            chunks = self.retriever.retrieve_relevant_chunks(
                query=user_message,
                document_ids=document_ids,
                top_k=8,
                similarity_threshold=0.1
            )
            
            if not chunks:
                logger.warning("No relevant chunks found")
                return {
                    **state,
                    "retrieved_chunks": [],
                    "context": "",
                    "status": "no_chunks_found"
                }
            
            # Build context from chunks
            context_parts = []
            source_chunk_ids = []
            
            for i, chunk in enumerate(chunks, 1):
                context_parts.append(
                    f"[Excerpt {i}] (Similarity: {chunk['similarity']:.2f})\n{chunk['chunk_text']}"
                )
                source_chunk_ids.append(chunk["id"])
            
            context = "\n\n".join(context_parts)
            
            logger.info(f"Retrieved {len(chunks)} relevant chunks")
            
            return {
                **state,
                "retrieved_chunks": chunks,
                "context": context,
                "source_chunk_ids": source_chunk_ids,
                "status": "chunks_retrieved"
            }
            
        except Exception as e:
            logger.error(f"Error retrieving chunks: {e}")
            return {**state, "error": str(e), "status": "error"}

    def _generate_rag_answer(self, state: QAChatState) -> QAChatState:
        """Generate answer using retrieved chunks."""
        try:
            user_message = state["user_message"]
            context = state.get("context", "")
            history = state.get("conversation_history", [])
            
            # Build conversation history string (includes summary + recent messages)
            history_str = ""
            if history:
                history_parts = []
                for msg in history:
                    if msg["role"] == "system":
                        # This is the summary
                        history_parts.append(msg["content"])
                    else:
                        role = "Student" if msg["role"] == "user" else "Assistant"
                        history_parts.append(f"{role}: {msg['content']}")
                history_str = "Previous Conversation:\n" + "\n".join(history_parts)
            
            # Check if chunks were found
            if not context:
                response_text = (
                    "I couldn't find relevant information in your documents to answer this question. "
                    "Could you try rephrasing your question or asking about a different topic from your materials?"
                )
                
                return {
                    **state,
                    "assistant_response": response_text,
                    "model_used": "gpt-4o-mini",
                    "status": "response_generated"
                }
            
            # Build messages
            messages = [
                SystemMessage(content=RAG_ANSWER_SYSTEM_PROMPT),
                HumanMessage(content=RAG_ANSWER_USER_PROMPT_TEMPLATE.format(
                    question=user_message,
                    context=context,
                    conversation_history=history_str
                ))
            ]
            
            # Generate response
            response = self.rag_llm.invoke(messages)
            
            return {
                **state,
                "assistant_response": str(response.content),  # type: ignore
                "model_used": "gpt-4o-mini",
                "status": "response_generated"
            }
            
        except Exception as e:
            logger.error(f"Error generating RAG answer: {e}")
            return {**state, "error": str(e), "status": "error"}

    def _save_message(self, state: QAChatState) -> QAChatState:
        """Save user message and assistant response to database."""
        try:
            conversation_id = state["conversation_id"]
            user_message = state["user_message"]
            assistant_response = state.get("assistant_response", "")
            source_chunk_ids = state.get("source_chunk_ids", [])
            
            # Save user message
            user_msg = ConversationMessage(
                conversation_id=conversation_id,
                role="user",
                content=user_message,
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(user_msg)
            
            # Save assistant response
            assistant_msg = ConversationMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_response,
                source_chunk_ids=json.dumps(source_chunk_ids) if source_chunk_ids else None,
                model_used=state.get("model_used"),
                tokens_used=state.get("tokens_used"),
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(assistant_msg)
            
            # Update conversation timestamp
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            if conversation:
                conversation.updated_at = datetime.now(timezone.utc)  # type: ignore
            
            self.db.commit()
            
            logger.info(f"Saved messages to conversation {conversation_id}")
            
            return {**state, "status": "messages_saved"}
            
        except Exception as e:
            logger.error(f"Error saving messages: {e}")
            self.db.rollback()
            return {**state, "error": str(e), "status": "error"}

    def _check_summarization(self, state: QAChatState) -> QAChatState:
        """Check if conversation needs summarization (when exceeding 10 messages)."""
        try:
            conversation_id = state["conversation_id"]
            
            # Get latest summary
            latest_summary = self.db.query(ConversationSummary).filter(
                ConversationSummary.conversation_id == conversation_id
            ).order_by(ConversationSummary.created_at.desc()).first()
            
            # Get all messages since last summary (or all if no summary exists)
            start_msg_id = latest_summary.end_message_id + 1 if latest_summary else 1
            
            messages_since_summary = self.db.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.id >= start_msg_id
            ).order_by(ConversationMessage.created_at).all()
            
            # When we have more than 10 messages, summarize the oldest 10
            if len(messages_since_summary) > 10:
                logger.info(f"Conversation {conversation_id} has {len(messages_since_summary)} messages, creating rolling summary")
                
                # Take the oldest 10 messages to summarize
                messages_to_summarize = messages_since_summary[:10]
                
                # Create new summary (combining with previous if exists)
                self._generate_summary(
                    conversation_id=conversation_id,
                    messages=messages_to_summarize,
                    previous_summary=str(latest_summary.summary) if latest_summary else None  # type: ignore
                )
            
            return {**state, "status": "completed"}
            
        except Exception as e:
            logger.error(f"Error checking summarization: {e}")
            # Don't fail the whole request if summarization fails
            return {**state, "status": "completed"}

    def _generate_summary(
        self, 
        conversation_id: int, 
        messages: List[ConversationMessage],
        previous_summary: Optional[str] = None
    ):
        """Generate and save conversation summary + update title (efficient single LLM call)."""
        try:
            # Format messages for summarization
            message_texts = []
            for msg in messages:
                role = "Student" if str(msg.role) == "user" else "Assistant"  # type: ignore
                message_texts.append(f"{role}: {str(msg.content)}")
            
            messages_str = "\n\n".join(message_texts)
            
            # Check if this is the first summary (to generate title)
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            needs_title = not conversation.title or conversation.title == "New Conversation" # type: ignore
            
            # Build prompt - include previous summary if exists
            if previous_summary:
                prompt = f"""Previous Summary:
{previous_summary}

New Messages:
{messages_str}

Create a new summary that combines the previous summary with these new messages. Keep only the main points and important information.

Format your response as JSON:
{{
    "summary": "your summary here"
}}"""
            else:
                # First summary - also generate title
                if needs_title: # type: ignore
                    prompt = f"""Conversation Messages:
{messages_str}

Generate both a conversation title and summary.

Requirements:
1. Title: Create a concise, descriptive title (3-7 words) that captures the main topic. Use the student's question language.
2. Summary: Summarize the key points, questions asked, and information provided (2-4 sentences).

Format your response as JSON:
{{
    "title": "your title here",
    "summary": "your summary here"
}}"""
                else:
                    prompt = SUMMARIZATION_USER_PROMPT_TEMPLATE.format(messages=messages_str) + """

Format your response as JSON:
{
    "summary": "your summary here"
}"""
            
            # Generate summary (and title if first time)
            summary_llm = LLMFactory.create_llm(
                temperature=0.5,
                json_mode=True
            )
            llm_messages = [
                SystemMessage(content=SUMMARIZATION_SYSTEM_PROMPT + "\n\nYou must respond with valid JSON only."),
                HumanMessage(content=prompt)
            ]
            
            result = summary_llm.invoke(llm_messages)
            response_text = result.content if hasattr(result, 'content') else str(result)
            
            # Parse JSON response
            import json
            response_data = json.loads(response_text) # type: ignore
            summary_text = response_data.get('summary', '')
            
            # Update conversation title if this is first summary and title was generated
            if needs_title and 'title' in response_data: # type: ignore
                conversation.title = response_data['title'][:255]  # Limit to column size # type: ignore
                logger.info(f"Generated title for conversation {conversation_id}: {conversation.title}") # type: ignore
            
            # Save summary
            summary = ConversationSummary(
                conversation_id=conversation_id,
                start_message_id=messages[0].id,
                end_message_id=messages[-1].id,
                summary=summary_text,
                message_count=len(messages),
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(summary)
            self.db.commit()
            
            logger.info(f"Generated summary for conversation {conversation_id}")
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            self.db.rollback()

    def process_message(
        self,
        conversation_id: int,
        user_id: int,
        message: str,
        document_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the Q&A agent.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            message: User's message
            document_ids: Optional list of document IDs to search

        Returns:
            Dict with response and metadata
        """
        initial_state: QAChatState = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "user_message": message,
            "document_ids": document_ids,
            "intent": None,
            "retrieved_chunks": None,
            "context": None,
            "conversation_history": [],
            "assistant_response": None,
            "source_chunk_ids": None,
            "tokens_used": None,
            "model_used": None,
            "status": "initialized",
            "error": None,
        }

        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)

            if final_state.get("error"):
                raise Exception(final_state["error"])

            return {
                "response": final_state["assistant_response"],
                "intent": final_state.get("intent"),
                "source_chunks": final_state.get("source_chunk_ids") or [],
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            raise
