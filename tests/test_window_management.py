"""Tests for conversation window management functionality."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from src.client import AnthropicClient, ConversationWindow

@pytest.fixture
def mock_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

@pytest.fixture
def window():
    """Create a test conversation window."""
    return ConversationWindow(max_tokens=1000, max_messages=10)

def test_window_initialization(window):
    """Test window initialization and default values."""
    assert window.max_tokens == 1000
    assert window.max_messages == 10
    assert len(window.messages) == 0
    assert window.token_count == 0

def test_window_add_message(window):
    """Test adding messages to window."""
    # Add messages
    window.add_message({"role": "user", "content": "Hello"})
    window.add_message({"role": "assistant", "content": "Hi there"})
    window.add_message({"role": "user", "content": "How are you?"})
    
    # Verify state
    assert len(window.messages) == 3
    assert window.messages[0]["role"] == "user"
    assert window.messages[0]["content"] == "Hello"
    assert window.token_count > 0

def test_window_max_messages(window):
    """Test window message limit enforcement."""
    # Add more messages than limit
    for i in range(15):
        window.add_message({"role": "user", "content": f"Message {i}"})
    
    # Verify limit enforcement
    assert len(window.messages) == window.max_messages
    assert window.messages[0]["content"] == "Message 5"
    assert window.messages[-1]["content"] == "Message 14"

def test_window_token_limit(window):
    """Test window token limit enforcement."""
    # Add a large message
    large_message = {"role": "user", "content": "A" * 5000}
    window.add_message(large_message)
    
    # Add regular messages
    for i in range(5):
        window.add_message({"role": "user", "content": f"Message {i}"})
    
    # Verify token limit
    assert window.token_count <= window.max_tokens
    assert len(window.messages) > 0

def test_window_clear(window):
    """Test clearing the window."""
    # Add messages
    for i in range(5):
        window.add_message({"role": "user", "content": f"Message {i}"})
    
    # Clear window
    window.clear()
    
    # Verify state
    assert len(window.messages) == 0
    assert window.token_count == 0

def test_window_get_messages(window):
    """Test retrieving messages from window."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm good"}
    ]
    
    # Add messages
    for msg in messages:
        window.add_message(msg)
    
    # Get messages with different parameters
    all_msgs = window.get_messages()
    assert len(all_msgs) == len(messages)
    
    user_msgs = window.get_messages(role="user")
    assert len(user_msgs) == 2
    assert all(msg["role"] == "user" for msg in user_msgs)
    
    recent_msgs = window.get_messages(limit=2)
    assert len(recent_msgs) == 2
    assert recent_msgs[-1]["content"] == "I'm good"

def test_window_message_ordering(window):
    """Test message ordering in window."""
    messages = [
        {"role": "user", "content": "First", "timestamp": datetime.now()},
        {"role": "assistant", "content": "Second", "timestamp": datetime.now() + timedelta(seconds=1)},
        {"role": "user", "content": "Third", "timestamp": datetime.now() + timedelta(seconds=2)}
    ]
    
    # Add messages out of order
    window.add_message(messages[1])
    window.add_message(messages[0])
    window.add_message(messages[2])
    
    # Verify order
    window_msgs = window.get_messages()
    assert len(window_msgs) == 3
    assert window_msgs[0]["content"] == "First"
    assert window_msgs[1]["content"] == "Second"
    assert window_msgs[2]["content"] == "Third"

def test_window_metadata(window):
    """Test window metadata handling."""
    # Add message with metadata
    window.add_message({
        "role": "user",
        "content": "Test message",
        "metadata": {
            "source": "user_input",
            "timestamp": datetime.now().isoformat(),
            "session_id": "test-123"
        }
    })
    
    # Verify metadata preservation
    msg = window.get_messages()[0]
    assert "metadata" in msg
    assert msg["metadata"]["source"] == "user_input"
    assert "timestamp" in msg["metadata"]
    assert msg["metadata"]["session_id"] == "test-123" 