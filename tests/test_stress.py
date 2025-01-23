"""Tests for system behavior under stress conditions."""
import pytest
import time
import threading
import multiprocessing
import psutil
import os
import signal
from pathlib import Path
from unittest.mock import patch, MagicMock
import anthropic
from datetime import datetime, timedelta
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

def test_system_limits(client):
    """Test system behavior at and beyond design limits."""
    # Test message size limits
    max_size_msg = "Test" * client.max_tokens
    with pytest.raises(ValueError):
        client.send_message(max_size_msg)
    
    # Test window size limits
    for i in range(client.max_window_size + 10):
        client.add_to_window(f"Message {i}")
    assert len(client.conversation.messages) == client.max_window_size
    
    # Test batch size limits
    large_batch = [f"Message {i}" for i in range(1000)]
    batches = list(client._split_into_batches(large_batch))
    assert all(len(batch) <= client.max_batch_size for batch in batches)
    
    # Test token limits
    assert client.conversation.token_count <= client.max_tokens

def test_recovery_mechanisms(client):
    """Test system recovery from various failure conditions."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Test recovery from API failures
        errors = [
            anthropic.APIStatusError(message="Rate limit", response=MagicMock(status_code=429), body={}),
            anthropic.APITimeoutError(request=MagicMock()),
            anthropic.APIConnectionError(request=MagicMock(), message="Connection failed"),
            Exception("Unknown error")
        ]
        
        for error in errors:
            # Simulate error then success
            mock_client.messages.create.side_effect = [error] * 3 + [MagicMock(
                content=[MagicMock(text="Success")]
            )]
            mock_client_class.return_value = mock_client
            
            # Attempt operation
            response = client.send_message("Test recovery")
            assert response == "Success"
            
            # Verify system state
            assert client.conversation is not None
            assert client.current_conversation_id is not None
    
    # Test recovery from resource exhaustion
    with pytest.raises(MemoryError):
        huge_data = ["x" * 1024 * 1024 for _ in range(1000)]  # Try to allocate too much memory
    
    # Verify system still functional
    response = client.send_message("Test after memory error")
    assert response == "Success"

def test_error_handling_under_load(client):
    """Test error handling while under heavy load."""
    def error_generator():
        """Generate various errors while system is under load."""
        errors = [
            anthropic.APIStatusError(message="Rate limit", response=MagicMock(status_code=429), body={}),
            anthropic.APITimeoutError(request=MagicMock()),
            anthropic.APIConnectionError(request=MagicMock(), message="Connection failed"),
            MemoryError("Out of memory"),
            Exception("Random error")
        ]
        while True:
            for error in errors:
                yield error
    
    error_gen = error_generator()
    
    def worker(worker_id):
        with patch('anthropic.Client') as mock_client_class:
            mock_client = MagicMock()
            
            for i in range(20):
                # Randomly inject errors
                if i % 3 == 0:
                    mock_client.messages.create.side_effect = next(error_gen)
                else:
                    mock_client.messages.create.return_value = MagicMock(
                        content=[MagicMock(text=f"Response {i}")]
                    )
                mock_client_class.return_value = mock_client
                
                try:
                    client.send_message(f"Message {i} from worker {worker_id}")
                except Exception:
                    pass  # Errors expected
    
    # Run multiple workers
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()
    
    # Verify system still functional
    assert client.conversation is not None
    assert hasattr(client, 'current_conversation_id')

def test_resource_exhaustion(client):
    """Test behavior under resource exhaustion conditions."""
    # Monitor resource usage
    initial_metrics = {
        'memory': psutil.Process().memory_info().rss,
        'cpu': psutil.Process().cpu_percent(),
        'threads': threading.active_count()
    }
    
    # Create resource pressure
    threads = []
    for _ in range(20):
        def stress_worker():
            large_data = ["x" * 1024 * 1024]  # 1MB per item
            while True:
                try:
                    large_data.append(large_data[-1])
                except MemoryError:
                    break
        
        thread = threading.Thread(target=stress_worker)
        thread.start()
        threads.append(thread)
    
    # Wait for threads to complete
    for thread in threads:
        thread.join()
    
    # Verify system can recover
    client.cleanup()
    
    # Check system still functional
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Success")]
        )
        mock_client_class.return_value = mock_client
        
        response = client.send_message("Test after resource exhaustion")
        assert response == "Success"

def test_data_consistency(client, temp_storage):
    """Test data consistency under stress."""
    conversation_data = {}
    
    def consistency_worker(worker_id):
        with patch('anthropic.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="Response")]
            )
            mock_client_class.return_value = mock_client
            
            # Create conversation
            conv_id = client.start_conversation(f"Worker {worker_id}")
            conversation_data[worker_id] = []
            
            # Add messages
            for i in range(10):
                msg = f"Message {i} from worker {worker_id}"
                client.send_message(msg)
                conversation_data[worker_id].append(msg)
                
                # Randomly save/load
                if i % 2 == 0:
                    client.save_conversation()
                    client.clear_conversation()
                    client.load_conversation(conv_id)
    
    # Run workers
    threads = []
    for i in range(5):
        thread = threading.Thread(target=consistency_worker, args=(i,))
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()
    
    # Verify data consistency
    conv_dir = Path(temp_storage) / "conversations"
    for worker_id, messages in conversation_data.items():
        conv_files = list(conv_dir.glob(f"*Worker_{worker_id}*.json"))
        assert len(conv_files) == 1
        
        # Load conversation and verify
        client.load_conversation(conv_files[0].stem)
        stored_messages = [msg["content"] for msg in client.conversation.get_messages()
                         if msg["role"] == "user"]
        assert stored_messages == messages

def test_failover_behavior(client):
    """Test system behavior during component failures."""
    def simulate_component_failure():
        """Simulate various component failures."""
        # Simulate encoder failure
        client.encoder = None
        
        # Simulate tokenizer failure
        client.tokenizer = None
        
        # Simulate conversation failure
        client.conversation = None
    
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create initial state
        client.start_conversation("Failover Test")
        client.send_message("Initial message")
        
        # Simulate failures
        simulate_component_failure()
        
        # Attempt recovery
        try:
            client.reinitialize()
            response = client.send_message("Test after failure")
            assert response == "Response"
        except Exception as e:
            pytest.fail(f"Failed to recover from component failure: {e}")
        
        # Verify components restored
        assert client.encoder is not None
        assert client.tokenizer is not None
        assert client.conversation is not None 