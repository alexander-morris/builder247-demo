"""HTTP server for Anthropic CLI tools."""
from typing import Dict, Any, Optional
import os
from pathlib import Path
import json
from datetime import datetime
import logging
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from .client import AnthropicClient

# Initialize FastAPI app
app = FastAPI(title="Anthropic CLI Tools")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize client
client = AnthropicClient(
    api_key=os.getenv("CLAUDE_API_KEY"),
    storage_dir=Path("/app/conversations"),
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    system: Optional[str] = None

class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    conversation_id: str

class ConversationRequest(BaseModel):
    """Conversation creation request model."""
    title: str
    metadata: Optional[Dict[str, Any]] = None

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> Dict[str, str]:
    """Send a message to Claude."""
    try:
        response = client.send_message(
            prompt=request.message,
            system=request.system
        )
        return {
            "response": response,
            "conversation_id": client.current_conversation_id
        }
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/conversations")
async def create_conversation(request: ConversationRequest) -> Dict[str, str]:
    """Create a new conversation."""
    try:
        conversation_id = client.start_conversation(
            title=request.title,
            metadata=request.metadata
        )
        return {"conversation_id": conversation_id}
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversations")
async def list_conversations() -> Dict[str, Any]:
    """List all conversations."""
    try:
        conversations = client.history_manager.list_conversations()
        return {"conversations": conversations}
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """Get conversation details and messages."""
    try:
        metadata = client.history_manager.get_conversation_metadata(conversation_id)
        messages = client.history_manager.get_messages(conversation_id)
        return {
            "metadata": metadata,
            "messages": messages
        }
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> Dict[str, str]:
    """Delete a conversation."""
    try:
        client.history_manager.delete_conversation(conversation_id)
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/conversations/{conversation_id}/load")
async def load_conversation(conversation_id: str) -> Dict[str, str]:
    """Load a conversation into memory."""
    try:
        client.load_conversation(conversation_id)
        return {"status": "loaded"}
    except Exception as e:
        logger.error(f"Error loading conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def start_background_tasks(app: FastAPI):
    """Start background tasks."""
    async def compress_old_messages():
        """Periodically compress old messages."""
        while True:
            try:
                client.conversation._maybe_compress_messages()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in background compression: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying

    asyncio.create_task(compress_old_messages())

@app.on_event("startup")
async def startup_event():
    """Run startup tasks."""
    start_background_tasks(app)

def main():
    """Run the server."""
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    main() 