"""Tests for system-level integration."""
import pytest
import os
import tempfile
import shutil
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import anthropic
from datetime import datetime, timedelta
from src.client import AnthropicClient

@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_env(monkeypatch, temp_storage):
    """Set up test environment variables."""
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("STORAGE_DIR", temp_storage)
    monkeypatch.setenv("MAX_RETRIES", "3")

@pytest.fixture
def client(mock_env, temp_storage):
    """Create a test client instance with temporary storage."""
    return AnthropicClient(storage_dir=temp_storage)

def test_full_message_flow(client):
    """Test complete message flow through the system."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        responses = [
            MagicMock(content=[MagicMock(text="First response")]),
            MagicMock(content=[MagicMock(text="Second response")]),
            MagicMock(content=[MagicMock(text="Final response")])
        ]
        mock_client.messages.create.side_effect = responses
        mock_client_class.return_value = mock_client
        
        # Start conversation
        conv_id = client.start_conversation("Test Flow")
        
        # Send multiple messages
        response1 = client.send_message("First message")
        response2 = client.send_message("Second message")
        response3 = client.send_message("Third message")
        
        # Verify responses
        assert response1 == "First response"
        assert response2 == "Second response"
        assert response3 == "Final response"
        
        # Verify conversation state
        messages = client.conversation.get_messages()
        assert len(messages) == 6  # 3 user messages + 3 assistant responses
        assert messages[0]["content"] == "First message"
        assert messages[-1]["content"] == "Final response"
        
        # Verify API calls
        assert mock_client.messages.create.call_count == 3
        for call in mock_client.messages.create.call_args_list:
            assert call[1]["model"] == "claude-3-sonnet-20240229"

def test_conversation_persistence(client, temp_storage):
    """Test conversation persistence and recovery."""
    # Create conversation with messages
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create and populate conversation
        conv_id = client.start_conversation("Persistence Test")
        client.send_message("Test message 1")
        client.send_message("Test message 2")
        
        # Save conversation state
        client.save_conversation()
        
        # Clear current state
        client.clear_conversation()
        assert len(client.conversation.messages) == 0
        
        # Load conversation
        client.load_conversation(conv_id)
        
        # Verify state restored
        messages = client.conversation.get_messages()
        assert len(messages) == 4  # 2 user messages + 2 responses
        assert messages[0]["content"] == "Test message 1"
        
        # Verify persistence files
        conv_file = Path(temp_storage) / "conversations" / f"{conv_id}.json"
        assert conv_file.exists()
        assert conv_file.stat().st_size > 0

def test_resource_management(client):
    """Test system resource management."""
    # Monitor resource usage
    initial_memory = client.get_memory_usage()
    
    # Generate load
    large_messages = ["Test message " * 1000 for _ in range(50)]
    
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Process messages
        for msg in large_messages:
            client.send_message(msg)
            
            # Verify resource constraints
            assert client.get_memory_usage() <= client.max_memory_mb * 1024 * 1024
            assert len(client.conversation.messages) <= client.max_window_size
            assert client.conversation.token_count <= client.max_tokens
    
    # Verify cleanup
    client.cleanup()
    final_memory = client.get_memory_usage()
    assert final_memory - initial_memory < 50 * 1024 * 1024  # Less than 50MB growth

def test_concurrent_operations(client):
    """Test system behavior under concurrent operations."""
    def conversation_worker(worker_id):
        with patch('anthropic.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=f"Response to worker {worker_id}")]
            )
            mock_client_class.return_value = mock_client
            
            # Create conversation
            conv_id = client.start_conversation(f"Worker {worker_id}")
            
            # Send messages
            for i in range(5):
                response = client.send_message(f"Message {i} from worker {worker_id}")
                assert response == f"Response to worker {worker_id}"
            
            # Save and clear
            client.save_conversation()
            client.clear_conversation()
    
    # Create multiple threads
    threads = []
    for i in range(3):
        thread = threading.Thread(target=conversation_worker, args=(i,))
        thread.start()
        threads.append(thread)
    
    # Wait for completion
    for thread in threads:
        thread.join()
    
    # Verify system state
    conv_dir = Path(client.storage_dir) / "conversations"
    conversation_files = list(conv_dir.glob("*.json"))
    assert len(conversation_files) == 3  # One file per worker

def test_system_recovery(client):
    """Test system recovery from various failure scenarios."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Simulate different failure scenarios
        scenarios = [
            anthropic.APIStatusError(message="Rate limit", response=MagicMock(status_code=429), body={}),
            anthropic.APITimeoutError(request=MagicMock()),
            anthropic.APIConnectionError(request=MagicMock(), message="Connection failed"),
            Exception("Unknown error")
        ]
        
        for error in scenarios:
            # Setup error then success
            mock_client.messages.create.side_effect = [error, MagicMock(
                content=[MagicMock(text="Success")]
            )]
            mock_client_class.return_value = mock_client
            
            # Attempt operation
            try:
                response = client.send_message("Test recovery")
                assert response == "Success"
            except Exception as e:
                if not isinstance(e, anthropic.APIError):
                    # Non-API errors should propagate
                    raise
            
            # Verify system state is valid
            assert client.conversation is not None
            assert hasattr(client, 'current_conversation_id')

def test_cleanup_procedures(client, temp_storage):
    """Test system cleanup procedures."""
    # Create test data
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create multiple conversations
        for i in range(3):
            conv_id = client.start_conversation(f"Cleanup Test {i}")
            client.send_message(f"Test message {i}")
            client.save_conversation()
    
    # Verify initial state
    conv_dir = Path(temp_storage) / "conversations"
    initial_files = list(conv_dir.glob("*.json"))
    assert len(initial_files) == 3
    
    # Perform cleanup
    client.cleanup(max_age_days=0)  # Clean all conversations
    
    # Verify cleanup
    remaining_files = list(conv_dir.glob("*.json"))
    assert len(remaining_files) == 0
    
    # Verify system still functional
    new_conv_id = client.start_conversation("New Conversation")
    assert new_conv_id is not None
    
    # Verify temp files cleaned
    temp_files = list(Path(temp_storage).glob("*.tmp"))
    assert len(temp_files) == 0 