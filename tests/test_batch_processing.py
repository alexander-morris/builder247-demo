"""Tests for batch processing and token counting functionality."""
import pytest
from unittest.mock import patch, MagicMock
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

def test_token_counting_accuracy(client):
    """Test accuracy of token counting for various inputs."""
    test_cases = [
        ("Hello world", 2),  # Basic case
        ("", 0),  # Empty string
        ("a" * 1000, None),  # Long string
        ("🌟 emoji test", None),  # Unicode/emoji
        ("Multi\nline\ntext", 3),  # Multiline
        ("Special @#$% chars!", None),  # Special characters
    ]
    
    for text, expected_min_tokens in test_cases:
        token_count = client._count_tokens(text)
        assert token_count > 0 if text else token_count == 0
        if expected_min_tokens:
            assert token_count >= expected_min_tokens

def test_batch_size_limits(client):
    """Test batch size limits and splitting."""
    # Create a large batch of messages
    messages = [f"Message {i}" for i in range(100)]
    
    # Process batch with different size limits
    for batch_size in [10, 20, 50]:
        client.max_batch_size = batch_size
        batches = list(client._split_into_batches(messages))
        
        # Verify batch sizes
        assert all(len(batch) <= batch_size for batch in batches)
        assert sum(len(batch) for batch in batches) == len(messages)

def test_batch_token_limits(client):
    """Test batch processing respects token limits."""
    # Create messages of varying lengths
    messages = [
        "Short message",
        "Medium length message with some more words",
        "A" * 1000,  # Long message
        "Another regular message",
        "B" * 500   # Medium-long message
    ]
    
    # Process with token limit
    client.max_batch_tokens = 1000
    batches = list(client._split_into_batches(messages))
    
    # Verify token limits
    for batch in batches:
        batch_tokens = sum(client._count_tokens(msg) for msg in batch)
        assert batch_tokens <= client.max_batch_tokens

def test_batch_processing_order(client):
    """Test that batch processing maintains message order."""
    messages = [f"Message {i}" for i in range(10)]
    
    with patch.object(client, '_process_batch') as mock_process:
        mock_process.side_effect = lambda batch: batch
        
        # Process messages
        results = client.process_batch(messages)
        
        # Verify order is maintained
        assert results == messages
        
        # Verify batches were processed in order
        call_args_list = mock_process.call_args_list
        processed_messages = []
        for call in call_args_list:
            processed_messages.extend(call[0][0])
        assert processed_messages == messages

def test_batch_error_handling(client):
    """Test error handling during batch processing."""
    messages = [f"Message {i}" for i in range(5)]
    
    with patch.object(client, '_process_batch') as mock_process:
        # Simulate errors for specific messages
        def process_with_errors(batch):
            return ["Error" if "2" in msg or "4" in msg else msg for msg in batch]
        
        mock_process.side_effect = process_with_errors
        
        # Process batch
        results = client.process_batch(messages)
        
        # Verify error handling
        assert len(results) == len(messages)
        assert results[2] == "Error"  # Message 2 should be error
        assert results[4] == "Error"  # Message 4 should be error
        assert all(results[i] == messages[i] for i in [0, 1, 3])  # Others should be unchanged 