"""Tests for component integration."""
import pytest
from unittest.mock import patch, MagicMock
import anthropic
from datetime import datetime
from src.client import AnthropicClient, ConversationWindow

@pytest.fixture
def mock_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

@pytest.fixture
def client(mock_env):
    """Create a test client instance."""
    return AnthropicClient()

def test_client_encoder_interaction(client):
    """Test interaction between client and encoder components."""
    # Test encoding/decoding flow
    test_message = "Test message with special chars: 🌟 @#$%"
    
    # Encode message
    encoded = client.encoder.encode(test_message)
    assert encoded is not None
    
    # Decode message
    decoded = client.encoder.decode(encoded)
    assert decoded == test_message
    
    # Test encoder with API interaction
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        response = client.send_message(test_message)
        assert response == "Response"
        
        # Verify encoder was used in API call
        call_args = mock_client.messages.create.call_args[1]
        assert "messages" in call_args
        assert isinstance(call_args["messages"][0]["content"], str)

def test_window_compression_interaction(client):
    """Test interaction between window management and compression."""
    # Create large message that should trigger compression
    large_message = "Test " * 1000
    
    # Add to window
    client.add_to_window(large_message)
    
    # Verify compression was applied
    window_messages = client.conversation.get_messages()
    assert len(window_messages) == 1
    
    # Verify message can be decompressed
    retrieved_message = client.conversation.get_message_content(0)
    assert retrieved_message == large_message
    
    # Test compression with window limits
    for i in range(10):
        client.add_to_window(f"Message {i} " * 100)
    
    # Verify older messages are compressed
    messages = client.conversation.get_messages()
    assert any(msg.get('_compressed') for msg in messages[:-5])
    assert not any(msg.get('_compressed') for msg in messages[-5:])

def test_batch_window_interaction(client):
    """Test interaction between batch processing and window management."""
    # Create batch of messages
    messages = [f"Message {i}" * (50 if i % 2 == 0 else 10) for i in range(10)]
    
    # Process batch
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Process messages
        client.process_batch(messages)
        
        # Verify window state
        window_messages = client.conversation.get_messages()
        assert len(window_messages) == len(messages)
        
        # Verify batch processing respected window limits
        assert client.conversation.token_count <= client.conversation.max_tokens
        assert len(window_messages) <= client.conversation.max_messages

def test_error_propagation(client):
    """Test error propagation between components."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError("API Error")
        mock_client_class.return_value = mock_client
        
        # Add some messages to window
        client.add_to_window("Message 1")
        client.add_to_window("Message 2")
        
        # Trigger error
        with pytest.raises(anthropic.APIError):
            client.send_message("Test message")
        
        # Verify window state is preserved
        assert len(client.conversation.messages) == 2
        assert client.conversation.messages[0]["content"] == "Message 1"
        
        # Verify client can continue after error
        mock_client.messages.create.side_effect = None
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Success")]
        )
        
        response = client.send_message("Another message")
        assert response == "Success"

def test_state_management(client):
    """Test state management across components."""
    # Set up mock API
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create conversation
        conv_id = client.start_conversation("Test Chat")
        
        # Add messages
        client.send_message("Message 1")
        client.send_message("Message 2")
        
        # Verify conversation state
        assert client.current_conversation_id == conv_id
        assert len(client.conversation.messages) == 4  # 2 user + 2 assistant messages
        
        # Clear conversation
        client.clear_conversation()
        
        # Verify state reset
        assert client.current_conversation_id is None
        assert len(client.conversation.messages) == 0
        
        # Load conversation
        client.load_conversation(conv_id)
        
        # Verify state restored
        assert client.current_conversation_id == conv_id
        assert len(client.conversation.messages) == 4

def test_resource_sharing(client):
    """Test resource sharing between components."""
    # Test shared tokenizer
    message = "Test message"
    token_count = client._count_tokens(message)
    window_token_count = client.conversation._count_tokens(message)
    assert token_count == window_token_count
    
    # Test shared encoder
    encoded = client.encoder.encode(message)
    window_encoded = client.conversation.encoder.encode(message)
    assert encoded == window_encoded
    
    # Test shared configuration
    assert client.max_tokens == client.conversation.max_tokens
    assert client.model == client.conversation.model

def test_concurrent_component_access(client):
    """Test concurrent access to shared components."""
    import threading
    
    def worker():
        for _ in range(10):
            # Access shared components
            client.tokenizer.encode("Test")
            client.encoder.encode("Test")
            client.add_to_window("Test message")
    
    # Create threads
    threads = []
    for _ in range(3):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)
    
    # Wait for completion
    for thread in threads:
        thread.join()
    
    # Verify components are still functional
    assert client._count_tokens("Test") > 0
    assert len(client.conversation.messages) > 0 