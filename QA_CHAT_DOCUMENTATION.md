# Q&A Chat Agent Documentation

## Overview

The Q&A Chat Agent is a professional LangGraph-based conversational AI system that provides intelligent document-based question answering with automatic routing between normal chat and RAG (Retrieval-Augmented Generation).

## Architecture

### Components

1. **QAChatAgent** (`app/core/agents/chat/qa_chat.py`)

   - Main orchestrator using LangGraph StateGraph
   - Handles intent classification, retrieval, and response generation
   - Manages conversation history and automatic summarization

2. **DocumentRetriever** (`app/core/helpers/retriever.py`)

   - Vector similarity search using pgvector
   - Cosine similarity with OpenAI embeddings (1024 dimensions)
   - Configurable top-k and similarity threshold

3. **Conversation API** (`app/api/v1/conversation.py`)

   - RESTful endpoints for chat functionality
   - Authentication and authorization
   - Conversation management (create, list, delete)

4. **Database Models** (`app/models/conversation.py`)
   - `Conversation`: Chat sessions
   - `ConversationMessage`: Individual Q&A messages
   - `ConversationSummary`: Auto-generated summaries every 5 Q&A pairs

## Features

### 1. Intent Routing

The agent automatically classifies user messages into two categories:

- **Normal Chat**: General conversation, greetings, study tips
- **Document Query**: Questions about uploaded document content

```python
# Classification happens automatically
user: "Hello!"
-> Routes to: normal_chat

user: "What are the key concepts in chapter 3?"
-> Routes to: document_query (RAG)
```

### 2. RAG (Retrieval-Augmented Generation)

For document queries:

1. Generate embedding for user question
2. Retrieve top-k relevant chunks (pgvector cosine similarity)
3. Build context from retrieved chunks
4. Generate answer using GPT-4o-mini with context
5. Track source chunks for citation

```python
# Example retrieval
retriever.retrieve_relevant_chunks(
    query="Explain photosynthesis",
    document_ids=[1, 2, 3],
    top_k=5,
    similarity_threshold=0.7
)
```

### 3. Automatic Summarization

Every 10 messages (5 Q&A pairs), the agent automatically:

1. Generates a concise summary of the conversation segment
2. Stores summary in `conversation_summaries` table
3. Uses summaries as memory for future context

### 4. Conversation History

- Loads last 10 messages (5 Q&A pairs) as context
- Maintains conversation continuity
- Stores source chunk IDs for RAG answers

## API Endpoints

### Create Conversation

```http
POST /api/v1/conversation/conversations
Authorization: Bearer <token>
Content-Type: application/json

{
  "document_ids": [1, 2, 3]  // Optional
}
```

**Response:**

```json
{
  "id": 1,
  "title": "New Conversation",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": null,
  "message_count": 0
}
```

### Send Message

```http
POST /api/v1/conversation/conversations/{conversation_id}/messages
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "What are the main topics in my biology notes?"
}
```

**Response:**

```json
{
  "conversation_id": 1,
  "user_message": "What are the main topics in my biology notes?",
  "assistant_response": "Based on your biology notes, the main topics are...",
  "intent": "document_query",
  "source_chunks": [12, 45, 67],
  "timestamp": "2024-01-15T10:31:00Z"
}
```

### Get Conversation History

```http
GET /api/v1/conversation/conversations/{conversation_id}?limit=50
Authorization: Bearer <token>
```

**Response:**

```json
{
  "conversation": {
    "id": 1,
    "title": "What are the main topics...",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:35:00Z",
    "message_count": 12
  },
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "What are the main topics?",
      "created_at": "2024-01-15T10:31:00Z"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "The main topics are...",
      "created_at": "2024-01-15T10:31:05Z"
    }
  ],
  "summaries": [
    "The student asked about main topics in biology notes. The assistant explained photosynthesis, cell structure, and genetics concepts."
  ]
}
```

### List Conversations

```http
GET /api/v1/conversation/conversations?skip=0&limit=20
Authorization: Bearer <token>
```

### Delete Conversation

```http
DELETE /api/v1/conversation/conversations/{conversation_id}
Authorization: Bearer <token>
```

## LangGraph Workflow

```
┌──────────────────────────┐
│  load_conversation_      │
│  history                 │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  classify_intent         │
└────────┬─────────────────┘
         │
         ├───────────────────┐
         ▼                   ▼
┌────────────────┐  ┌────────────────┐
│  normal_chat   │  │ retrieve_chunks│
└────────┬───────┘  └────────┬───────┘
         │                   │
         │                   ▼
         │          ┌────────────────┐
         │          │ generate_rag_  │
         │          │ answer         │
         │          └────────┬───────┘
         │                   │
         └───────┬───────────┘
                 ▼
         ┌────────────────┐
         │  save_message  │
         └────────┬───────┘
                  ▼
         ┌────────────────────┐
         │ check_summarization│
         └────────────────────┘
```

## Configuration

### LLM Settings

```python
# Intent classification: Temperature 0.0 (deterministic)
classification_llm = LLMFactory.create_llm(temperature=0.0, json_mode=True)

# Normal chat: Temperature 0.7 (creative)
chat_llm = LLMFactory.create_llm(temperature=0.7)

# RAG answers: Temperature 0.3 (factual)
rag_llm = LLMFactory.create_llm(temperature=0.3)

# Summarization: Temperature 0.5 (balanced)
summary_llm = LLMFactory.create_llm(temperature=0.5, json_mode=True)
```

### Retrieval Settings

```python
# Default retrieval parameters
top_k = 5  # Number of chunks to retrieve
similarity_threshold = 0.7  # Minimum cosine similarity (0-1)
```

### Summarization Trigger

```python
# Summarize every 10 messages (5 Q&A pairs)
SUMMARIZATION_THRESHOLD = 10
```

## Database Schema

### conversations

| Column     | Type         | Description                        |
| ---------- | ------------ | ---------------------------------- |
| id         | INTEGER      | Primary key                        |
| user_id    | INTEGER      | Foreign key to users               |
| title      | VARCHAR(255) | Auto-generated from first question |
| created_at | TIMESTAMP    | Creation time                      |
| updated_at | TIMESTAMP    | Last update time                   |

### conversation_messages

| Column           | Type         | Description                      |
| ---------------- | ------------ | -------------------------------- |
| id               | INTEGER      | Primary key                      |
| conversation_id  | INTEGER      | Foreign key to conversations     |
| role             | VARCHAR(20)  | 'user' or 'assistant'            |
| content          | TEXT         | Message content                  |
| source_chunk_ids | TEXT         | JSON array of chunk IDs          |
| tokens_used      | INTEGER      | API usage tracking               |
| model_used       | VARCHAR(100) | Model name (e.g., "gpt-4o-mini") |
| created_at       | TIMESTAMP    | Message time                     |

### conversation_summaries

| Column           | Type      | Description                  |
| ---------------- | --------- | ---------------------------- |
| id               | INTEGER   | Primary key                  |
| conversation_id  | INTEGER   | Foreign key to conversations |
| start_message_id | INTEGER   | First message in segment     |
| end_message_id   | INTEGER   | Last message in segment      |
| summary          | TEXT      | Summary content              |
| message_count    | INTEGER   | Usually 10 (5 Q&A pairs)     |
| created_at       | TIMESTAMP | Summary creation time        |

## Error Handling

The agent includes comprehensive error handling:

1. **Intent Classification Failure**: Defaults to `document_query`
2. **No Relevant Chunks Found**: Returns friendly message asking to rephrase
3. **Database Errors**: Rollback and return 500 error
4. **Summarization Failure**: Logs error but doesn't fail the request
5. **Authorization**: Returns 403 for unauthorized access

## Usage Example

```python
from app.core.agents.chat.qa_chat import QAChatAgent
from app.db.base import get_db

db = next(get_db())
agent = QAChatAgent(db)

result = agent.process_message(
    conversation_id=1,
    user_id=123,
    message="What is photosynthesis?",
    document_ids=[5, 6, 7]
)

print(result["response"])
# "Photosynthesis is a process used by plants..."

print(result["intent"])
# "document_query"

print(result["source_chunks"])
# [12, 34, 56]
```

## Testing

Run the conversation migration:

```bash
alembic upgrade head
```

Test the API:

```bash
# Create conversation
curl -X POST http://localhost:8000/api/v1/conversation/conversations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_ids": [1, 2]}'

# Send message
curl -X POST http://localhost:8000/api/v1/conversation/conversations/1/messages \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the key concepts?"}'
```

## Performance Considerations

1. **Vector Search**: Uses pgvector's optimized `<=>` operator for cosine distance
2. **Context Window**: Limits history to last 10 messages to avoid token limits
3. **Batch Processing**: EmbeddingService supports batching up to 2048 texts
4. **Database Indexing**: Indexes on `user_id`, `conversation_id` for fast queries

## Future Enhancements

- [ ] Multi-document conversation support
- [ ] Export conversation as PDF/markdown
- [ ] Conversation sharing between users
- [ ] Advanced context window management
- [ ] Streaming responses for real-time chat
- [ ] Voice input/output support
- [ ] Conversation analytics dashboard

## Troubleshooting

### "No relevant chunks found" message

- Check if documents have been processed (embeddings generated)
- Lower `similarity_threshold` if too strict
- Verify document IDs belong to user

### Summarization not triggered

- Check message count (needs 10 messages since last summary)
- Review logs for summarization errors
- Verify `conversation_summaries` table exists

### Slow responses

- Check pgvector index on `embedding_vector` column
- Reduce `top_k` parameter
- Consider caching frequently accessed chunks

## Support

For issues or questions, refer to:

- Backend documentation: `BACKEND_SUMMARY.md`
- API documentation: FastAPI interactive docs at `/docs`
- Development guide: `DEVELOPMENT.md`
