"""Tests for data persistence workflow."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
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

def test_data_persistence_workflow(client, temp_storage):
    """Test complete data persistence workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create multiple conversations
        conversations = []
        for i in range(3):
            # Start conversation
            conv_id = client.start_conversation(f"Conversation {i}")
            conversations.append(conv_id)
            
            # Add messages
            for j in range(3):
                client.send_message(f"Message {j} in conversation {i}")
            
            # Save conversation
            client.save_conversation()
            client.clear_conversation()
        
        # Verify all conversations saved
        conv_dir = Path(temp_storage) / "conversations"
        saved_files = list(conv_dir.glob("*.json"))
        assert len(saved_files) == 3
        
        # Load and verify each conversation
        for conv_id in conversations:
            client.load_conversation(conv_id)
            messages = client.conversation.get_messages()
            assert len(messages) == 6  # 3 user messages + 3 responses
            client.clear_conversation()

def test_data_recovery_workflow(client, temp_storage):
    """Test data recovery workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create and save conversation
        conv_id = client.start_conversation("Recovery Test")
        client.send_message("Test message")
        client.save_conversation()
        
        # Simulate crash by clearing memory
        client.clear_conversation()
        client.conversation = None
        
        # Recover conversation
        client.load_conversation(conv_id)
        
        # Verify state
        messages = client.conversation.get_messages()
        assert len(messages) == 2  # 1 user message + 1 response
        assert messages[0]["content"] == "Test message"

def test_data_consistency_workflow(client, temp_storage):
    """Test data consistency workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create conversation with metadata
        conv_id = client.start_conversation(
            "Consistency Test",
            metadata={"test_id": "123", "timestamp": "2024-01-23"}
        )
        
        # Add messages with metadata
        for i in range(3):
            client.send_message(
                f"Message {i}",
                metadata={"sequence": i, "type": "test"}
            )
        
        # Save and reload
        client.save_conversation()
        client.clear_conversation()
        client.load_conversation(conv_id)
        
        # Verify conversation metadata
        conv_meta = client.get_conversation_metadata(conv_id)
        assert conv_meta["title"] == "Consistency Test"
        assert conv_meta["test_id"] == "123"
        
        # Verify message metadata
        messages = client.conversation.get_messages()
        for i, msg in enumerate(messages[::2]):  # User messages only
            assert msg["metadata"]["sequence"] == i
            assert msg["metadata"]["type"] == "test" 