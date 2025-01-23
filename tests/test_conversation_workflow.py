"""Tests for conversation workflow."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
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

def test_complete_conversation_workflow(client):
    """Test complete conversation workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            MagicMock(content=[MagicMock(text="Hello! How can I help?")]),
            MagicMock(content=[MagicMock(text="I can help with that.")]),
            MagicMock(content=[MagicMock(text="Here's the solution...")]),
            MagicMock(content=[MagicMock(text="Goodbye!")])]
        mock_client_class.return_value = mock_client
        
        # Start conversation
        conv_id = client.start_conversation("Technical Support")
        
        # Initial greeting
        response = client.send_message("Hi, I need help with an issue")
        assert "help" in response.lower()
        
        # Problem description
        response = client.send_message("My application is running slowly")
        assert "help" in response.lower()
        
        # Technical discussion
        response = client.send_message("I think it's a memory leak")
        assert "solution" in response.lower()
        
        # Wrap up
        response = client.send_message("Thanks for your help")
        assert "goodbye" in response.lower()
        
        # Verify conversation history
        messages = client.conversation.get_messages()
        assert len(messages) == 8  # 4 user messages + 4 assistant responses
        
        # Save conversation
        client.save_conversation()
        
        # Verify persistence
        conv_file = Path(client.storage_dir) / "conversations" / f"{conv_id}.json"
        assert conv_file.exists()
        
        # Load conversation
        client.clear_conversation()
        client.load_conversation(conv_id)
        loaded_messages = client.conversation.get_messages()
        assert len(loaded_messages) == len(messages) 