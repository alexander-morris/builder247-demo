"""Tests for error handling functionality."""
import pytest
from unittest.mock import patch, MagicMock
import anthropic
from src.client import AnthropicClient

@pytest.fixture
def mock_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

@pytest.fixture
def client(mock_env):
    """Create a test client instance."""
    return AnthropicClient()

def test_api_error_handling(client):
    """Test handling of various API errors."""
    error_cases = [
        (anthropic.APIStatusError, {"message": "Rate limit exceeded", "status_code": 429}),
        (anthropic.APITimeoutError, {"request": MagicMock()}),
        (anthropic.APIConnectionError, {"request": MagicMock(), "message": "Connection failed"}),
        (anthropic.APIError, {"message": "Unknown error"})
    ]
    
    for error_class, error_kwargs in error_cases:
        with patch('anthropic.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = error_class(**error_kwargs)
            mock_client_class.return_value = mock_client
            
            with pytest.raises(error_class):
                client.send_message("Test message")

def test_invalid_input_handling(client):
    """Test handling of invalid input parameters."""
    invalid_inputs = [
        (None, "Message cannot be None"),
        ("", "Message cannot be empty"),
        ("A" * 100000, "Message exceeds maximum length"),
        (123, "Message must be a string"),
        ({"invalid": "type"}, "Message must be a string")
    ]
    
    for invalid_input, expected_error in invalid_inputs:
        with pytest.raises(ValueError, match=expected_error):
            client.send_message(invalid_input)

def test_token_limit_handling(client):
    """Test handling of token limit violations."""
    # Test message that exceeds token limit
    with patch.object(client, '_count_tokens') as mock_count:
        mock_count.return_value = client.max_tokens + 100
        
        with pytest.raises(ValueError, match="exceeds maximum token limit"):
            client.send_message("Test message")

def test_rate_limit_recovery(client):
    """Test recovery from rate limiting."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Simulate rate limit then success
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        
        mock_client.messages.create.side_effect = [
            anthropic.APIStatusError(message="Rate limit exceeded", response=mock_response, body={}),
            MagicMock(content=[MagicMock(text="Success")])
        ]
        mock_client_class.return_value = mock_client
        
        response = client.send_message("Test message")
        assert response == "Success"
        assert mock_client.messages.create.call_count == 2

def test_connection_error_retry(client):
    """Test retry behavior for connection errors."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_request = MagicMock()
        
        # Simulate connection errors then success
        mock_client.messages.create.side_effect = [
            anthropic.APIConnectionError(request=mock_request, message="Connection failed"),
            anthropic.APIConnectionError(request=mock_request, message="Connection failed"),
            MagicMock(content=[MagicMock(text="Success")])
        ]
        mock_client_class.return_value = mock_client
        
        response = client.send_message("Test message")
        assert response == "Success"
        assert mock_client.messages.create.call_count == 3

def test_malformed_response_handling(client):
    """Test handling of malformed API responses."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Test various malformed responses
        malformed_responses = [
            MagicMock(content=None),
            MagicMock(content=[]),
            MagicMock(content=[MagicMock(text=None)]),
            MagicMock(content=[MagicMock(text="")])
        ]
        
        for response in malformed_responses:
            mock_client.messages.create.return_value = response
            mock_client_class.return_value = mock_client
            
            with pytest.raises(ValueError, match="Invalid response"):
                client.send_message("Test message")

def test_system_error_handling(client):
    """Test handling of system-level errors."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Test system errors
        system_errors = [
            MemoryError("Out of memory"),
            OSError("File system error"),
            RuntimeError("Unknown error")
        ]
        
        for error in system_errors:
            mock_client.messages.create.side_effect = error
            mock_client_class.return_value = mock_client
            
            with pytest.raises(type(error)):
                client.send_message("Test message")

def test_cleanup_after_error(client):
    """Test resource cleanup after errors."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Test error")
        mock_client_class.return_value = mock_client
        
        # Add some messages before error
        client.add_to_window("Message 1")
        client.add_to_window("Message 2")
        
        # Trigger error
        with pytest.raises(Exception):
            client.send_message("Test message")
        
        # Verify cleanup
        assert client.conversation.token_count > 0  # Should preserve valid messages
        assert len(client.conversation.messages) == 2  # Should preserve valid messages 