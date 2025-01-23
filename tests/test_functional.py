"""Tests for complete functional workflows."""
import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import anthropic
from src.client import AnthropicClient

@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage directory."""
    return str(tmp_path)

@pytest.fixture
def mock_env(monkeypatch, temp_storage):
    """Set up test environment variables."""
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("STORAGE_DIR", temp_storage)
    monkeypatch.setenv("MAX_RETRIES", "3")

@pytest.fixture
def client(mock_env, temp_storage):
    """Create a test client instance."""
    return AnthropicClient(storage_dir=temp_storage)

def test_complete_user_workflow(client):
    """Test a complete user interaction workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            MagicMock(content=[MagicMock(text="Hello! I can help with that.")]),
            MagicMock(content=[MagicMock(text="Here's the solution...")]),
            MagicMock(content=[MagicMock(text="Let me clarify...")]),
            MagicMock(content=[MagicMock(text="You're welcome!")])
        ]
        mock_client_class.return_value = mock_client
        
        # Start conversation
        conv_id = client.start_conversation("Technical Support")
        assert conv_id is not None
        
        # Initial request
        response = client.send_message("I need help with API integration")
        assert "help" in response.lower()
        
        # Technical discussion
        response = client.send_message("How do I handle rate limits?")
        assert "solution" in response.lower()
        
        # Follow-up question
        response = client.send_message("Can you explain that again?")
        assert "clarify" in response.lower()
        
        # Wrap up
        response = client.send_message("Thanks!")
        assert "welcome" in response.lower()
        
        # Verify conversation history
        messages = client.conversation.get_messages()
        assert len(messages) == 8  # 4 user messages + 4 assistant responses
        
        # Save and verify persistence
        client.save_conversation()
        conv_file = Path(temp_storage) / "conversations" / f"{conv_id}.json"
        assert conv_file.exists()
        
        # Load and verify data
        with open(conv_file) as f:
            data = json.load(f)
            assert len(data["messages"]) == 8
            assert data["title"] == "Technical Support"

def test_api_interaction_workflow(client):
    """Test API interaction patterns."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Test successful API call
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Success")]
        )
        mock_client_class.return_value = mock_client
        
        response = client.send_message("Test message")
        assert response == "Success"
        
        # Test rate limiting
        mock_client.messages.create.side_effect = [
            anthropic.APIStatusError(message="Rate limit", response=MagicMock(status_code=429), body={}),
            MagicMock(content=[MagicMock(text="Success after retry")])
        ]
        
        response = client.send_message("Test rate limit")
        assert response == "Success after retry"
        
        # Test connection error recovery
        mock_client.messages.create.side_effect = [
            anthropic.APIConnectionError(request=MagicMock(), message="Connection failed"),
            MagicMock(content=[MagicMock(text="Success after connection")])
        ]
        
        response = client.send_message("Test connection")
        assert response == "Success after connection"

def test_data_persistence_workflow(client, temp_storage):
    """Test data persistence and recovery."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create multiple conversations
        conversations = []
        for i in range(3):
            conv_id = client.start_conversation(f"Conversation {i}")
            conversations.append(conv_id)
            
            # Add messages
            for j in range(3):
                client.send_message(f"Message {j}")
            client.save_conversation()
        
        # Verify persistence
        conv_dir = Path(temp_storage) / "conversations"
        saved_files = list(conv_dir.glob("*.json"))
        assert len(saved_files) == 3
        
        # Test recovery
        client.clear_conversation()
        for conv_id in conversations:
            client.load_conversation(conv_id)
            messages = client.conversation.get_messages()
            assert len(messages) == 6  # 3 user messages + 3 responses
            client.clear_conversation()

def test_error_recovery_workflow(client):
    """Test error recovery scenarios."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Test recovery from API errors
        errors = [
            anthropic.APIStatusError(message="Rate limit", response=MagicMock(status_code=429), body={}),
            anthropic.APITimeoutError(request=MagicMock()),
            anthropic.APIConnectionError(request=MagicMock(), message="Connection failed")
        ]
        
        for error in errors:
            # Simulate error then success
            mock_client.messages.create.side_effect = [error] * 2 + [
                MagicMock(content=[MagicMock(text="Success")])
            ]
            mock_client_class.return_value = mock_client
            
            response = client.send_message("Test recovery")
            assert response == "Success"
            
            # Verify system state
            assert client.conversation is not None
            assert client.current_conversation_id is not None
        
        # Test recovery from resource exhaustion
        with pytest.raises(MemoryError):
            huge_data = ["x" * 1024 * 1024 for _ in range(1000)]
        
        # Verify system still functional
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Still working")]
        )
        response = client.send_message("Test after memory error")
        assert response == "Still working"

def test_performance_metrics_workflow(client):
    """Test performance metrics collection."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Record initial metrics
        start_time = time.time()
        initial_memory = client.get_memory_usage()
        
        # Generate load
        for _ in range(10):
            client.send_message("Test message")
        
        # Record final metrics
        end_time = time.time()
        final_memory = client.get_memory_usage()
        
        # Verify metrics
        duration = end_time - start_time
        assert duration / 10 < 1.0  # Average response time under 1 second
        assert final_memory <= initial_memory * 1.5  # Memory growth within 50%
        
        # Verify logs
        log_file = list(Path(client.storage_dir).glob("logs/prompt_log_*.jsonl"))[0]
        log_entries = [json.loads(line) for line in log_file.read_text().splitlines()]
        
        assert len(log_entries) >= 10
        for entry in log_entries:
            assert "timestamp" in entry
            assert "level" in entry
            assert "message" in entry

def test_security_measures_workflow(client):
    """Test security measures and controls."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Test API key validation
        with pytest.raises(ValueError):
            AnthropicClient(api_key="invalid-key")
        
        # Test input validation
        with pytest.raises(ValueError):
            client.send_message("" * 100000)  # Too long
        
        with pytest.raises(ValueError):
            client.send_message("")  # Empty
        
        # Test file permissions
        client.save_conversation()
        conv_file = list(Path(client.storage_dir).glob("conversations/*.json"))[0]
        assert oct(conv_file.stat().st_mode)[-3:] in ('600', '640', '644')  # Restrictive permissions
        
        # Test data sanitization
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="<script>alert('xss')</script>")]
        )
        response = client.send_message("Test XSS")
        assert "<script>" not in response
