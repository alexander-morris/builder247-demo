"""Tests for container integration."""
import pytest
import docker
import os
import time
import requests
import json
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

@pytest.fixture
def docker_compose():
    """Set up and tear down docker-compose environment."""
    os.system("docker-compose -f docker-compose.test.yml up -d")
    time.sleep(5)  # Wait for services to be ready
    yield
    os.system("docker-compose -f docker-compose.test.yml down -v")

@pytest.fixture
def docker_client():
    """Create Docker client."""
    return docker.from_env()

def test_service_communication(docker_compose, docker_client):
    """Test communication between services."""
    agent = docker_client.containers.get("anthropic-agent")
    test_service = docker_client.containers.get("test-service")
    
    # Test API communication
    result = test_service.exec_run(
        "curl -X POST http://agent:8000/api/v1/message -H 'Content-Type: application/json' -d '{\"message\":\"test\"}'"
    )
    assert result.exit_code == 0
    response = json.loads(result.output)
    assert "response" in response
    
    # Test shared volume access
    agent.exec_run("echo 'test data' > /app/data/shared/test.txt")
    result = test_service.exec_run("cat /app/data/shared/test.txt")
    assert result.exit_code == 0
    assert b"test data" in result.output

def test_data_persistence(docker_compose, docker_client):
    """Test data persistence across container restarts."""
    agent = docker_client.containers.get("anthropic-agent")
    
    # Create test data
    agent.exec_run("""python -c "
from src.client import AnthropicClient
client = AnthropicClient()
conv_id = client.start_conversation('Test')
client.send_message('Test message')
client.save_conversation()
    """")
    
    # Get conversation ID
    result = agent.exec_run("ls /app/data/conversations")
    conv_file = result.output.decode().strip()
    
    # Restart container
    agent.restart()
    time.sleep(5)
    
    # Verify data persists
    result = agent.exec_run(f"cat /app/data/conversations/{conv_file}")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "Test message" in str(data)

def test_logging_system(docker_compose, docker_client):
    """Test logging system integration."""
    agent = docker_client.containers.get("anthropic-agent")
    
    # Generate logs from different components
    test_cases = [
        "client.send_message('Test message')",
        "client.process_batch(['Message 1', 'Message 2'])",
        "client.start_conversation('Test')"
    ]
    
    for test in test_cases:
        agent.exec_run(f"""python -c "
from src.client import AnthropicClient
client = AnthropicClient()
{test}
        """")
    
    # Check log aggregation
    result = agent.exec_run("cat /app/logs/prompt_log_*.jsonl")
    logs = result.output.decode()
    
    assert "Test message" in logs
    assert "Message 1" in logs
    assert "Test" in logs
    
    # Check log format
    log_lines = logs.strip().split("\n")
    for line in log_lines:
        log_entry = json.loads(line)
        assert "timestamp" in log_entry
        assert "level" in log_entry
        assert "message" in log_entry

def test_monitoring(docker_compose, docker_client):
    """Test monitoring integration."""
    agent = docker_client.containers.get("anthropic-agent")
    
    # Get metrics endpoint
    response = requests.get("http://localhost:8000/metrics")
    assert response.status_code == 200
    metrics = response.json()
    
    # Check required metrics
    assert "memory_usage" in metrics
    assert "cpu_usage" in metrics
    assert "request_count" in metrics
    assert "error_count" in metrics
    
    # Generate load
    for _ in range(5):
        requests.post(
            "http://localhost:8000/api/v1/message",
            json={"message": "test"}
        )
    
    # Check metrics updated
    response = requests.get("http://localhost:8000/metrics")
    updated_metrics = response.json()
    assert updated_metrics["request_count"] > metrics["request_count"]

def test_scaling(docker_compose, docker_client):
    """Test service scaling."""
    # Scale up agent service
    os.system("docker-compose -f docker-compose.test.yml up -d --scale agent=3")
    time.sleep(5)
    
    # Verify containers
    containers = docker_client.containers.list(
        filters={"name": "anthropic-agent"}
    )
    assert len(containers) == 3
    
    # Test load distribution
    def send_requests():
        for _ in range(10):
            response = requests.post(
                "http://localhost:8000/api/v1/message",
                json={"message": "test"}
            )
            assert response.status_code == 200
    
    # Send concurrent requests
    threads = []
    for _ in range(3):
        thread = threading.Thread(target=send_requests)
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()
    
    # Check load distribution
    for container in containers:
        stats = container.stats(stream=False)
        assert stats["cpu_stats"]["cpu_usage"]["total_usage"] > 0

def test_updates_rollbacks(docker_compose, docker_client):
    """Test update and rollback procedures."""
    agent = docker_client.containers.get("anthropic-agent")
    
    # Get initial version
    result = agent.exec_run("cat /app/VERSION")
    initial_version = result.output.decode().strip()
    
    # Simulate update
    agent.exec_run("echo '2.0.0' > /app/VERSION")
    agent.restart()
    time.sleep(5)
    
    # Verify update
    result = agent.exec_run("cat /app/VERSION")
    assert result.output.decode().strip() == "2.0.0"
    
    # Test rollback
    agent.exec_run(f"echo '{initial_version}' > /app/VERSION")
    agent.restart()
    time.sleep(5)
    
    # Verify rollback
    result = agent.exec_run("cat /app/VERSION")
    assert result.output.decode().strip() == initial_version
    
    # Verify functionality after rollback
    response = requests.post(
        "http://localhost:8000/api/v1/message",
        json={"message": "test after rollback"}
    )
    assert response.status_code == 200 