"""Performance tests for containerized agent."""
import os
import time
import pytest
import docker
import psutil
import requests
import threading
import statistics
from pathlib import Path
from typing import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

@pytest.fixture(scope="session")
def docker_compose():
    """Start services with docker-compose."""
    import subprocess
    
    # Start services
    subprocess.run(
        ["docker-compose", "up", "-d", "agent"],
        check=True
    )
    
    # Wait for agent to be healthy
    for _ in range(30):  # 30 second timeout
        try:
            response = requests.get("http://localhost:8080/health")
            if response.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Agent failed to become healthy")
    
    yield
    
    # Cleanup
    subprocess.run(
        ["docker-compose", "down", "-v"],
        check=True
    )

def test_memory_usage_under_load(docker_compose):
    """Test memory usage under load."""
    client = docker.from_env()
    container = client.containers.get("anthropic-agent")
    
    def get_memory_stats():
        stats = container.stats(stream=False)
        return stats["memory_stats"]["usage"]
    
    # Get baseline memory usage
    baseline_memory = get_memory_stats()
    
    # Generate load with concurrent requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for _ in range(50):
            futures.append(executor.submit(
                container.exec_run,
                'python -c "from src.client import AnthropicClient; '
                'client = AnthropicClient(); '
                'client.send_message(\'Test memory usage\' * 100)"'  # Large message
            ))
        
        # Monitor memory usage during load
        peak_memory = baseline_memory
        while futures:
            done, futures = as_completed(futures), []
            current_memory = get_memory_stats()
            peak_memory = max(peak_memory, current_memory)
    
    # Verify memory usage
    assert peak_memory < baseline_memory * 3  # Should not grow more than 3x
    
    # Wait for memory to stabilize
    time.sleep(10)
    final_memory = get_memory_stats()
    assert final_memory < baseline_memory * 1.5  # Should return close to baseline

def test_cpu_usage_patterns(docker_compose):
    """Test CPU usage patterns."""
    client = docker.from_env()
    container = client.containers.get("anthropic-agent")
    
    def get_cpu_percent():
        stats = container.stats(stream=False)
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                   stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                      stats["precpu_stats"]["system_cpu_usage"]
        return (cpu_delta / system_delta) * 100.0
    
    # Get baseline CPU usage
    baseline_cpu = get_cpu_percent()
    cpu_measurements = []
    
    # Generate load
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for _ in range(20):
            futures.append(executor.submit(
                container.exec_run,
                'python -c "from src.client import AnthropicClient; '
                'client = AnthropicClient(); '
                'client.send_message(\'Test CPU usage\')"'
            ))
        
        # Monitor CPU usage
        while futures:
            done, futures = as_completed(futures), []
            cpu_measurements.append(get_cpu_percent())
    
    # Calculate statistics
    avg_cpu = statistics.mean(cpu_measurements)
    max_cpu = max(cpu_measurements)
    
    # Verify CPU usage
    assert max_cpu < 80.0  # Should not saturate CPU
    assert avg_cpu < 50.0  # Average should be reasonable

def test_disk_io_performance(docker_compose):
    """Test disk I/O performance."""
    client = docker.from_env()
    container = client.containers.get("anthropic-agent")
    
    # Measure write performance
    start_time = time.time()
    large_data = "x" * 1000000  # 1MB of data
    write_times = []
    
    for _ in range(10):
        before = time.time()
        result = container.exec_run(
            'python -c "from src.client import AnthropicClient; '
            'client = AnthropicClient(); '
            f'client.send_message(\'{large_data}\')"'
        )
        assert result.exit_code == 0
        write_times.append(time.time() - before)
    
    # Measure read performance
    read_times = []
    result = container.exec_run('ls -la /app/logs/prompt_log_*.jsonl')
    log_files = result.output.decode().split("\n")
    
    for log_file in log_files:
        if not log_file.strip():
            continue
        before = time.time()
        result = container.exec_run(f'cat /app/logs/{log_file}')
        assert result.exit_code == 0
        read_times.append(time.time() - before)
    
    # Calculate I/O statistics
    avg_write_time = statistics.mean(write_times)
    avg_read_time = statistics.mean(read_times)
    
    # Verify I/O performance
    assert avg_write_time < 1.0  # Should write 1MB in less than 1 second
    assert avg_read_time < 0.1  # Should read logs quickly

def test_network_latency(docker_compose):
    """Test network request latency."""
    client = docker.from_env()
    container = client.containers.get("anthropic-agent")
    
    latencies = []
    
    # Measure request latency
    for _ in range(50):
        start_time = time.time()
        result = container.exec_run(
            'python -c "from src.client import AnthropicClient; '
            'client = AnthropicClient(); '
            'client.send_message(\'Test latency\')"'
        )
        assert result.exit_code == 0
        latencies.append(time.time() - start_time)
        time.sleep(0.1)  # Avoid rate limiting
    
    # Calculate latency statistics
    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
    
    # Verify latency
    assert avg_latency < 1.0  # Average should be under 1 second
    assert p95_latency < 2.0  # 95% should be under 2 seconds

def test_concurrent_requests(docker_compose):
    """Test handling of concurrent requests."""
    client = docker.from_env()
    container = client.containers.get("anthropic-agent")
    
    # Track request statistics
    successful_requests = 0
    failed_requests = 0
    response_times = []
    lock = threading.Lock()
    
    def make_request():
        nonlocal successful_requests, failed_requests
        start_time = time.time()
        result = container.exec_run(
            'python -c "from src.client import AnthropicClient; '
            'client = AnthropicClient(); '
            'client.send_message(\'Test concurrent requests\')"'
        )
        response_time = time.time() - start_time
        
        with lock:
            response_times.append(response_time)
            if result.exit_code == 0:
                successful_requests += 1
            else:
                failed_requests += 1
    
    # Start concurrent requests
    threads = []
    for _ in range(20):
        thread = threading.Thread(target=make_request)
        thread.start()
        threads.append(thread)
        time.sleep(0.1)  # Stagger requests
    
    # Wait for all requests to complete
    for thread in threads:
        thread.join()
    
    # Calculate statistics
    total_requests = successful_requests + failed_requests
    success_rate = (successful_requests / total_requests) * 100
    avg_response_time = statistics.mean(response_times)
    
    # Verify performance
    assert success_rate > 90.0  # At least 90% should succeed
    assert avg_response_time < 2.0  # Average response under 2 seconds

def test_load_recovery(docker_compose):
    """Test system recovery after heavy load."""
    client = docker.from_env()
    container = client.containers.get("anthropic-agent")
    
    def get_system_metrics():
        stats = container.stats(stream=False)
        return {
            'memory': stats["memory_stats"]["usage"],
            'cpu_percent': (stats["cpu_stats"]["cpu_usage"]["total_usage"] -
                          stats["precpu_stats"]["cpu_usage"]["total_usage"]) /
                         (stats["cpu_stats"]["system_cpu_usage"] -
                          stats["precpu_stats"]["system_cpu_usage"]) * 100.0
        }
    
    # Get baseline metrics
    baseline = get_system_metrics()
    
    # Generate heavy load
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for _ in range(50):
            futures.append(executor.submit(
                container.exec_run,
                'python -c "from src.client import AnthropicClient; '
                'client = AnthropicClient(); '
                'client.send_message(\'Test load\' * 100)"'
            ))
        for future in as_completed(futures):
            pass
    
    # Wait for system to stabilize
    time.sleep(30)
    
    # Get recovery metrics
    recovered = get_system_metrics()
    
    # Verify recovery
    assert recovered['memory'] <= baseline['memory'] * 1.2  # Within 20% of baseline
    assert recovered['cpu_percent'] <= baseline['cpu_percent'] * 1.2

def test_resource_efficiency(docker_compose):
    """Test resource efficiency over time."""
    client = docker.from_env()
    container = client.containers.get("anthropic-agent")
    
    # Monitor resource usage during normal operation
    memory_usage = []
    cpu_usage = []
    
    for _ in range(10):
        # Send a request
        result = container.exec_run(
            'python -c "from src.client import AnthropicClient; '
            'client = AnthropicClient(); '
            'client.send_message(\'Test efficiency\')"'
        )
        assert result.exit_code == 0
        
        # Get metrics
        stats = container.stats(stream=False)
        memory_usage.append(stats["memory_stats"]["usage"])
        
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                   stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                      stats["precpu_stats"]["system_cpu_usage"]
        cpu_usage.append((cpu_delta / system_delta) * 100.0)
        
        time.sleep(1)
    
    # Calculate efficiency metrics
    memory_variation = statistics.stdev(memory_usage) / statistics.mean(memory_usage)
    cpu_variation = statistics.stdev(cpu_usage) / statistics.mean(cpu_usage)
    
    # Verify stable resource usage
    assert memory_variation < 0.2  # Less than 20% variation
    assert cpu_variation < 0.3  # Less than 30% variation 