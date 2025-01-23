"""Tests for container functionality."""
import pytest
import docker
import os
import time
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock

@pytest.fixture
def docker_client():
    """Create Docker client."""
    return docker.from_env()

@pytest.fixture
def container(docker_client):
    """Create and manage test container."""
    # Build test image
    image, _ = docker_client.images.build(
        path=".",
        dockerfile="Dockerfile",
        tag="anthropic-agent-test"
    )
    
    # Create and start container
    container = docker_client.containers.run(
        "anthropic-agent-test",
        environment={
            "CLAUDE_API_KEY": "test-key",
            "LOG_LEVEL": "DEBUG"
        },
        volumes={
            "/tmp/anthropic-test": {
                "bind": "/app/data",
                "mode": "rw"
            }
        },
        ports={
            "8000/tcp": None  # Random port
        },
        detach=True,
        remove=True
    )
    
    # Wait for container to be ready
    time.sleep(2)
    
    yield container
    
    # Cleanup
    container.stop()

def test_container_build(docker_client):
    """Test container build process."""
    # Build image
    image, logs = docker_client.images.build(
        path=".",
        dockerfile="Dockerfile",
        tag="anthropic-agent-test"
    )
    
    # Verify image
    assert image.tags[0] == "anthropic-agent-test:latest"
    
    # Check image properties
    image_info = docker_client.images.get(image.id).attrs
    
    # Verify Python version
    assert "3.12" in str(image_info["Config"]["Env"])
    
    # Verify non-root user
    assert "USER agent" in str(image_info["Config"]["Cmd"])
    
    # Verify volume mounts
    assert "/app/data" in str(image_info["Config"]["Volumes"])
    
    # Verify exposed ports
    assert "8000/tcp" in image_info["Config"]["ExposedPorts"]

def test_environment_setup(container):
    """Test container environment configuration."""
    # Check environment variables
    env = container.exec_run("env").output.decode()
    assert "CLAUDE_API_KEY=test-key" in env
    assert "LOG_LEVEL=DEBUG" in env
    assert "PYTHONPATH=/app" in env
    
    # Check Python version
    python_version = container.exec_run("python --version").output.decode()
    assert "Python 3.12" in python_version
    
    # Check installed packages
    pip_list = container.exec_run("pip list").output.decode()
    required_packages = ["anthropic", "pytest", "psutil"]
    for package in required_packages:
        assert package in pip_list

def test_volume_mounts(container):
    """Test volume mount configuration."""
    # Check mount points
    mounts = container.attrs["Mounts"]
    assert any(mount["Destination"] == "/app/data" for mount in mounts)
    
    # Test write access
    test_file = "test.txt"
    container.exec_run(f"touch /app/data/{test_file}")
    
    # Verify file exists
    result = container.exec_run(f"ls /app/data/{test_file}")
    assert result.exit_code == 0
    
    # Clean up
    container.exec_run(f"rm /app/data/{test_file}")

def test_permissions(container):
    """Test container permissions and security."""
    # Check user
    user_info = container.exec_run("id").output.decode()
    assert "uid=" in user_info
    assert "gid=" in user_info
    assert "agent" in user_info
    
    # Check file permissions
    app_perms = container.exec_run("ls -l /app").output.decode()
    assert "drwxr-xr-x" in app_perms  # Readable but not writable by others
    
    # Test restricted operations
    restricted_ops = [
        "sudo ls",  # No sudo
        "apt-get update",  # No package management
        "curl example.com"  # No network tools
    ]
    
    for op in restricted_ops:
        result = container.exec_run(op)
        assert result.exit_code != 0

def test_health_check(container):
    """Test container health check endpoint."""
    # Get container port
    port = container.ports["8000/tcp"][0]["HostPort"]
    
    # Test health endpoint
    response = requests.get(f"http://localhost:{port}/health")
    assert response.status_code == 200
    
    health_data = response.json()
    assert "status" in health_data
    assert health_data["status"] == "healthy"
    assert "version" in health_data

def test_resource_limits(container):
    """Test container resource limits."""
    # Check memory limit
    memory_limit = container.attrs["HostConfig"]["Memory"]
    assert memory_limit > 0  # Memory limit set
    
    # Check CPU limit
    cpu_limit = container.attrs["HostConfig"]["NanoCpus"]
    assert cpu_limit > 0  # CPU limit set
    
    # Test memory constraint
    result = container.exec_run("""python -c "
import numpy as np
try:
    # Try to allocate more memory than limit
    data = np.zeros((1024*1024*1024, 8))
except MemoryError:
    exit(0)
exit(1)
    """")
    assert result.exit_code == 0  # Should fail with MemoryError

def test_logging_configuration(container):
    """Test container logging setup."""
    # Check log directory
    log_dir = container.exec_run("ls -l /app/logs").output.decode()
    assert "prompt_log" in log_dir
    
    # Generate some logs
    container.exec_run("""python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
logging.debug('Test debug message')
logging.info('Test info message')
logging.error('Test error message')
    """")
    
    # Check log content
    logs = container.exec_run("cat /app/logs/prompt_log_*.jsonl").output.decode()
    assert "Test debug message" in logs
    assert "Test info message" in logs
    assert "Test error message" in logs

def test_cleanup_procedures(container):
    """Test container cleanup procedures."""
    # Create test files
    container.exec_run("touch /app/data/test1.tmp")
    container.exec_run("touch /app/data/test2.tmp")
    
    # Run cleanup
    container.exec_run("python -c 'from src.client import cleanup; cleanup()'")
    
    # Verify cleanup
    remaining_files = container.exec_run("ls /app/data/*.tmp").output.decode()
    assert not remaining_files  # No temp files should remain
    
    # Check system state
    ps_output = container.exec_run("ps aux").output.decode()
    assert "python" in ps_output  # Main process should still be running 