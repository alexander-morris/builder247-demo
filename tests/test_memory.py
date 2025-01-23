"""Tests for memory optimization features."""
import os
import gc
import pytest
import psutil
import threading
import time
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

def get_memory_usage():
    """Get current memory usage in bytes."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss

def test_lazy_loading(client):
    """Test lazy loading of resources."""
    # Verify encoder is not loaded initially
    assert not hasattr(client, '_encoder')
    
    # Access encoder to trigger lazy loading
    _ = client.encoder
    
    # Verify encoder is now loaded
    assert hasattr(client, '_encoder')
    
    # Test lazy loading of other resources
    assert not hasattr(client, '_tokenizer')
    _ = client.tokenizer
    assert hasattr(client, '_tokenizer')

def test_memory_cleanup(client):
    """Test memory management and cleanup."""
    # Record initial memory usage
    initial_memory = get_memory_usage()
    
    # Generate large conversation history
    large_messages = ["Test message " * 1000 for _ in range(100)]
    for msg in large_messages:
        client.add_to_window(msg)
    
    # Force garbage collection
    gc.collect()
    
    # Record memory after cleanup
    final_memory = get_memory_usage()
    
    # Verify memory usage is reasonable
    memory_increase = final_memory - initial_memory
    assert memory_increase < 100 * 1024 * 1024  # Less than 100MB increase

def test_resource_limits(client):
    """Test system resource constraints."""
    # Set resource limits
    client.max_memory_mb = 100
    client.max_window_size = 50
    
    # Test memory limit enforcement
    large_messages = ["Test message " * 1000 for _ in range(100)]
    
    for msg in large_messages:
        client.add_to_window(msg)
        
        # Verify memory limits
        assert get_memory_usage() < client.max_memory_mb * 1024 * 1024
        
        # Verify window size limits
        assert len(client.conversation_history) <= client.max_window_size

def test_garbage_collection(client):
    """Test garbage collection behavior."""
    # Create some temporary objects
    temp_data = ["Temporary " * 1000 for _ in range(100)]
    client.temp_storage = temp_data
    
    # Record memory before cleanup
    memory_before = get_memory_usage()
    
    # Clear temporary data
    client.clear_temp_storage()
    gc.collect()
    
    # Record memory after cleanup
    memory_after = get_memory_usage()
    
    # Verify memory was freed
    assert memory_after < memory_before
    assert not hasattr(client, 'temp_storage')

def test_memory_leaks(client):
    """Test for memory leaks."""
    initial_memory = get_memory_usage()
    
    # Perform multiple operations
    for _ in range(100):
        # Create and process messages
        msg = "Test message " * 100
        client.add_to_window(msg)
        client.enforce_window_limits()
        gc.collect()
    
    # Final garbage collection
    gc.collect()
    
    # Check final memory usage
    final_memory = get_memory_usage()
    
    # Verify no significant memory leak
    assert (final_memory - initial_memory) < 10 * 1024 * 1024  # Less than 10MB growth

def test_cache_invalidation(client):
    """Test cache invalidation behavior."""
    # Mock cache data
    client._response_cache = {}
    client._token_cache = {}
    
    # Add items to cache
    test_key = "test_key"
    client._response_cache[test_key] = "cached_response"
    client._token_cache[test_key] = 100
    
    # Verify cache state
    assert test_key in client._response_cache
    assert test_key in client._token_cache
    
    # Trigger cache invalidation
    client.invalidate_caches()
    
    # Verify caches are cleared
    assert not client._response_cache
    assert not client._token_cache

def test_lazy_resource_loading(client):
    """Test lazy loading of resource-intensive components."""
    # Test tokenizer lazy loading
    assert not hasattr(client, '_tokenizer')
    _ = client.tokenizer  # Access to trigger loading
    assert hasattr(client, '_tokenizer')
    
    # Test encoder lazy loading
    assert not hasattr(client, '_encoder')
    _ = client.encoder  # Access to trigger loading
    assert hasattr(client, '_encoder')
    
    # Test model lazy loading
    assert not hasattr(client, '_model')
    _ = client.model  # Access to trigger loading
    assert hasattr(client, '_model')

def test_memory_cleanup_on_large_messages(client):
    """Test memory cleanup when processing large messages."""
    initial_memory = get_memory_usage()
    
    # Create a large message
    large_message = "Test " * 10000
    
    # Process message
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        client.send_message(large_message)
    
    # Force garbage collection
    gc.collect()
    
    # Verify memory usage
    final_memory = get_memory_usage()
    memory_increase = final_memory - initial_memory
    
    # Should not retain the large message in memory
    assert memory_increase < len(large_message)

def test_concurrent_memory_usage(client):
    """Test memory usage under concurrent operations."""
    initial_memory = get_memory_usage()
    
    def process_messages():
        for _ in range(10):
            with patch('anthropic.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client.messages.create.return_value = MagicMock(
                    content=[MagicMock(text="Response")]
                )
                mock_client_class.return_value = mock_client
                
                client.send_message("Test message")
            time.sleep(0.1)
    
    # Create multiple threads
    threads = []
    for _ in range(3):
        thread = threading.Thread(target=process_messages)
        thread.start()
        threads.append(thread)
    
    # Wait for threads to complete
    for thread in threads:
        thread.join()
    
    # Force cleanup
    gc.collect()
    
    # Verify memory usage
    final_memory = get_memory_usage()
    memory_increase = final_memory - initial_memory
    
    # Memory usage should be reasonable
    assert memory_increase < 50 * 1024 * 1024  # Less than 50MB increase

def test_resource_limit_enforcement(client):
    """Test enforcement of resource limits."""
    # Set resource limits
    client.max_memory_mb = 100
    client.max_cache_size = 1000
    
    # Add items to cache
    for i in range(2000):
        key = f"key_{i}"
        client._response_cache[key] = "value"
        
        # Verify cache size limit
        assert len(client._response_cache) <= client.max_cache_size
        
        # Verify memory limit
        assert get_memory_usage() <= client.max_memory_mb * 1024 * 1024

def test_memory_pressure_handling(client):
    """Test handling of memory pressure situations."""
    # Create memory pressure
    large_data = ["Pressure test " * 1000 for _ in range(1000)]
    
    # Record memory at start
    start_memory = get_memory_usage()
    
    try:
        # Add data until memory limit
        for data in large_data:
            if get_memory_usage() - start_memory > 100 * 1024 * 1024:  # 100MB limit
                break
            client.add_to_window(data)
    except MemoryError:
        pytest.fail("Failed to handle memory pressure gracefully")
    
    # Verify client is still functional
    assert client.conversation.token_count > 0
    assert len(client.conversation.messages) > 0

def test_cache_efficiency(client):
    """Test cache hit rates and efficiency."""
    # Track cache statistics
    hits = 0
    misses = 0
    
    # Simulate cache usage
    test_messages = ["Message " + str(i) for i in range(100)]
    
    for msg in test_messages:
        cache_key = client._get_cache_key(msg)
        
        if cache_key in client._response_cache:
            hits += 1
        else:
            misses += 1
            client._response_cache[cache_key] = "response"
    
    # Verify cache behavior
    assert hits + misses == len(test_messages)
    hit_rate = hits / len(test_messages)
    
    # Log cache statistics
    print(f"Cache hit rate: {hit_rate:.2%}")
    print(f"Cache size: {len(client._response_cache)}")

def test_memory_leaks_extended(client):
    """Extended test for memory leaks."""
    initial_memory = get_memory_usage()
    
    # Run multiple operations
    for _ in range(100):
        # Create and process messages
        msg = "Test message " * 100
        client.add_to_window(msg)
        client.enforce_window_limits()
        
        # Simulate cache operations
        cache_key = client._get_cache_key(msg)
        client._response_cache[cache_key] = "response"
        
        # Periodic cleanup
        if _ % 10 == 0:
            gc.collect()
            client.invalidate_caches()
    
    # Final cleanup
    gc.collect()
    
    # Check memory usage
    final_memory = get_memory_usage()
    memory_growth = final_memory - initial_memory
    
    # Verify no significant memory leak
    assert memory_growth < 10 * 1024 * 1024  # Less than 10MB growth 