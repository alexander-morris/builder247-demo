"""Tests for system load and performance."""
import pytest
import time
import threading
import multiprocessing
import psutil
import os
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

def get_system_metrics():
    """Get current system metrics."""
    process = psutil.Process()
    return {
        'memory': process.memory_info().rss,
        'cpu_percent': process.cpu_percent(),
        'io_counters': process.io_counters(),
        'threads': process.num_threads()
    }

def test_concurrent_message_processing(client):
    """Test performance under concurrent message load."""
    num_threads = 10
    messages_per_thread = 50
    metrics = {'start': get_system_metrics()}
    
    def worker():
        with patch('anthropic.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="Response")]
            )
            mock_client_class.return_value = mock_client
            
            for i in range(messages_per_thread):
                client.send_message(f"Test message {i}")
    
    # Create and start threads
    start_time = time.time()
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)
    
    # Wait for completion
    for thread in threads:
        thread.join()
    
    # Record metrics
    end_time = time.time()
    metrics['end'] = get_system_metrics()
    duration = end_time - start_time
    
    # Calculate performance metrics
    total_messages = num_threads * messages_per_thread
    messages_per_second = total_messages / duration
    memory_per_message = (metrics['end']['memory'] - metrics['start']['memory']) / total_messages
    
    # Verify performance meets requirements
    assert messages_per_second >= 10  # At least 10 messages/second
    assert memory_per_message < 1024 * 1024  # Less than 1MB per message
    assert metrics['end']['threads'] <= num_threads + 5  # Limited thread growth

def test_batch_processing_efficiency(client):
    """Test efficiency of batch message processing."""
    batch_sizes = [10, 50, 100, 200]
    metrics = {}
    
    for batch_size in batch_sizes:
        messages = [f"Test message {i}" for i in range(batch_size)]
        
        with patch('anthropic.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="Response")]
            )
            mock_client_class.return_value = mock_client
            
            # Measure batch processing
            start_metrics = get_system_metrics()
            start_time = time.time()
            
            client.process_batch(messages)
            
            duration = time.time() - start_time
            end_metrics = get_system_metrics()
            
            metrics[batch_size] = {
                'duration': duration,
                'memory_delta': end_metrics['memory'] - start_metrics['memory'],
                'messages_per_second': batch_size / duration
            }
    
    # Verify batch processing efficiency
    for size, data in metrics.items():
        # Larger batches should be more efficient
        if size > 10:
            assert data['messages_per_second'] > metrics[10]['messages_per_second']
        # Memory usage should scale sub-linearly
        assert data['memory_delta'] / size < metrics[10]['memory_delta'] / 10

def test_memory_usage_under_load(client):
    """Test memory usage patterns under heavy load."""
    initial_metrics = get_system_metrics()
    large_messages = ["Test message " * 1000 for _ in range(100)]
    memory_samples = []
    
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Process messages and monitor memory
        for i, msg in enumerate(large_messages):
            client.send_message(msg)
            
            if i % 10 == 0:
                memory_samples.append(get_system_metrics()['memory'])
    
    # Verify memory usage patterns
    max_memory = max(memory_samples)
    final_memory = memory_samples[-1]
    
    assert max_memory <= initial_metrics['memory'] * 3  # No more than 3x growth
    assert final_memory <= initial_metrics['memory'] * 2  # Cleanup effective

def test_cpu_utilization(client):
    """Test CPU utilization patterns."""
    cpu_samples = []
    sampling_interval = 0.1  # seconds
    
    def cpu_monitor():
        while len(cpu_samples) < 50:  # 5 seconds of monitoring
            cpu_samples.append(psutil.cpu_percent(interval=sampling_interval))
    
    # Start CPU monitoring
    monitor_thread = threading.Thread(target=cpu_monitor)
    monitor_thread.start()
    
    # Generate load
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        for _ in range(20):
            client.send_message("Test message" * 100)
    
    monitor_thread.join()
    
    # Analyze CPU usage
    avg_cpu = sum(cpu_samples) / len(cpu_samples)
    max_cpu = max(cpu_samples)
    
    assert avg_cpu <= 80  # Average CPU usage below 80%
    assert max_cpu <= 95  # Peak CPU usage below 95%

def test_io_performance(client, temp_storage):
    """Test I/O performance under load."""
    initial_io = psutil.Process().io_counters()
    large_messages = ["Test message " * 1000 for _ in range(50)]
    
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        start_time = time.time()
        
        # Process messages with persistence
        for msg in large_messages:
            client.send_message(msg)
            client.save_conversation()
    
        duration = time.time() - start_time
    
    final_io = psutil.Process().io_counters()
    io_bytes = final_io.write_bytes - initial_io.write_bytes
    
    # Calculate I/O metrics
    io_mb_per_sec = (io_bytes / 1024 / 1024) / duration
    
    # Verify I/O performance
    assert io_mb_per_sec <= 50  # No more than 50MB/s I/O
    assert duration / len(large_messages) <= 0.1  # Max 100ms per message

def test_network_latency(client):
    """Test network latency handling."""
    latencies = [0.1, 0.5, 1.0, 2.0]  # seconds
    metrics = {}
    
    for latency in latencies:
        with patch('anthropic.Client') as mock_client_class:
            mock_client = MagicMock()
            
            # Simulate network latency
            def delayed_response(*args, **kwargs):
                time.sleep(latency)
                return MagicMock(content=[MagicMock(text="Response")])
            
            mock_client.messages.create.side_effect = delayed_response
            mock_client_class.return_value = mock_client
            
            # Measure response time
            start_time = time.time()
            client.send_message("Test message")
            response_time = time.time() - start_time
            
            metrics[latency] = response_time
    
    # Verify latency handling
    for latency, response_time in metrics.items():
        # Response time should be close to latency
        assert abs(response_time - latency) <= 0.1  # 100ms tolerance
        # Higher latency shouldn't cause failures
        assert response_time > 0

def test_load_recovery(client):
    """Test system recovery after heavy load."""
    # Generate heavy load
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Create load
        for _ in range(100):
            client.send_message("Test message" * 100)
    
    # Record metrics before cleanup
    pre_cleanup = get_system_metrics()
    
    # Trigger cleanup
    client.cleanup()
    
    # Record metrics after cleanup
    post_cleanup = get_system_metrics()
    
    # Verify recovery
    assert post_cleanup['memory'] < pre_cleanup['memory']
    assert post_cleanup['threads'] <= pre_cleanup['threads']
    
    # Verify system is still responsive
    response = client.send_message("Test message")
    assert response == "Response" 