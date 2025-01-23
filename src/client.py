"""
Anthropic API client wrapper with tool integration support.
"""
from typing import List, Dict, Any, Optional
import os
import json
import time
import psutil
from pathlib import Path
from dotenv import load_dotenv
import anthropic
import html

class AnthropicClient:
    """Wrapper for Anthropic API client with tool integration."""
    
    def __init__(self, api_key: Optional[str] = None, storage_dir: str = "./data", model: str = "claude-3-opus-20240229"):
        """Initialize the client with API key and storage configuration."""
        load_dotenv()
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("API key not provided and CLAUDE_API_KEY not found in environment")
            
        self.client = anthropic.Client(api_key=self.api_key)
        self.model = model
        self.storage_dir = Path(storage_dir)
        self.conversation = Conversation()
        self.current_conversation_id = None
        
        # Create storage directories
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        (self.storage_dir / "conversations").mkdir(exist_ok=True)
        (self.storage_dir / "logs").mkdir(exist_ok=True)
        
        # Set limits
        self.max_tokens = 4096
        self.max_window_size = 100
        self.max_batch_size = 50
        
    def start_conversation(self, title: str) -> str:
        """Start a new conversation with a title."""
        self.conversation = Conversation(title=title)
        self.current_conversation_id = f"{int(time.time())}_{title.replace(' ', '_')}"
        return self.current_conversation_id
    
    def send_message(self, message: str) -> str:
        """Send a message and return the response."""
        if not message:
            raise ValueError("Message cannot be empty")
        if len(message) > self.max_tokens:
            raise ValueError(f"Message exceeds maximum length of {self.max_tokens} tokens")
            
        try:
            # Add user message
            self.conversation.add_message("user", message)
            
            # Get API response
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": m["role"], "content": m["content"]} 
                         for m in self.conversation.get_messages()]
            )
            
            # Extract and sanitize response
            assistant_message = html.escape(response.content[0].text)
            self.conversation.add_message("assistant", assistant_message)
            
            # Log interaction
            self._log_interaction(message, assistant_message)
            
            return assistant_message
            
        except Exception as e:
            self._log_interaction(message, str(e), level="ERROR")
            raise
    
    def save_conversation(self) -> None:
        """Save the current conversation to storage."""
        if not self.current_conversation_id:
            return
            
        conv_file = self.storage_dir / "conversations" / f"{self.current_conversation_id}.json"
        with open(conv_file, "w") as f:
            json.dump(self.conversation.to_dict(), f)
            
        # Set restrictive permissions
        conv_file.chmod(0o600)
    
    def load_conversation(self, conversation_id: str) -> None:
        """Load a conversation from storage."""
        conv_file = self.storage_dir / "conversations" / f"{conversation_id}.json"
        if not conv_file.exists():
            raise ValueError(f"Conversation {conversation_id} not found")
            
        with open(conv_file) as f:
            data = json.load(f)
            self.conversation = Conversation.from_dict(data)
            self.current_conversation_id = conversation_id
    
    def clear_conversation(self) -> None:
        """Clear the current conversation state."""
        self.conversation = Conversation()
        self.current_conversation_id = None
    
    def get_memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        return psutil.Process().memory_info().rss
    
    def _log_interaction(self, message: str, response: str, level: str = "INFO") -> None:
        """Log an interaction to the log file."""
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
            "response": response
        }
        
        log_file = self.storage_dir / "logs" / f"prompt_log_{time.strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a") as f:
            json.dump(log_entry, f)
            f.write("\n")
    
    def _split_into_batches(self, items: List[Any], batch_size: Optional[int] = None) -> List[List[Any]]:
        """Split a list into batches."""
        batch_size = batch_size or self.max_batch_size
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    
    def add_to_window(self, message: str) -> None:
        """Add a message to the conversation window."""
        self.conversation.add_message("user", message)
        if len(self.conversation.messages) > self.max_window_size:
            self.conversation.messages = self.conversation.messages[-self.max_window_size:]

class Conversation:
    """Class to manage conversation state."""
    
    def __init__(self, title: str = "Untitled"):
        """Initialize a conversation."""
        self.title = title
        self.messages: List[Dict[str, Any]] = []
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get all messages in the conversation."""
        return self.messages
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary."""
        return {
            "title": self.title,
            "messages": self.messages
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        """Create conversation from dictionary."""
        conv = cls(title=data["title"])
        conv.messages = data["messages"]
        return conv 