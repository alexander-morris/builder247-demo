"""Tests for interactive container functionality."""
import os
import pytest
import docker
import subprocess
from pathlib import Path
import time
import pexpect
from pexpect.popen_spawn import PopenSpawn

@pytest.fixture(scope="module")
def docker_container():
    """Start a Docker container for testing."""
    client = docker.from_env()
    
    # Build the image
    image, _ = client.images.build(
        path=".",
        tag="anthropic-agent:test",
        rm=True
    )
    
    # Start container
    container = client.containers.run(
        "anthropic-agent:test",
        detach=True,
        tty=True,
        stdin_open=True,
        volumes={
            str(Path.cwd() / "logs"): {"bind": "/app/logs", "mode": "rw"},
            str(Path.cwd() / "conversations"): {"bind": "/app/conversations", "mode": "rw"}
        }
    )
    
    # Wait for container to be ready
    time.sleep(2)
    
    yield container
    
    # Cleanup
    container.stop()
    container.remove()
    client.images.remove("anthropic-agent:test")

def test_prompt_startup(docker_container):
    """Test that the prompt starts correctly."""
    # Get container logs
    logs = docker_container.logs().decode()
    
    # Verify welcome message
    assert "Welcome to the container prompt" in logs
    assert "(container)" in logs

def test_create_file(docker_container):
    """Test creating a file through the prompt."""
    # Execute create command
    result = docker_container.exec_run(
        'python -c "print(\'create hello-world.txt Hello, World!\\n\')" | python -m src.prompt_handler',
        tty=True
    )
    
    # Verify command output
    output = result.output.decode()
    assert "Created file: /app/hello-world.txt" in output
    
    # Verify file exists
    result = docker_container.exec_run('cat /app/hello-world.txt')
    assert result.exit_code == 0
    assert result.output.decode().strip() == "Hello, World!"

def test_verify_file(docker_container):
    """Test verifying a file through the prompt."""
    # Execute verify command
    result = docker_container.exec_run(
        'python -c "print(\'verify hello-world.txt\\n\')" | python -m src.prompt_handler',
        tty=True
    )
    
    # Verify command output
    output = result.output.decode()
    assert "File exists: /app/hello-world.txt" in output
    assert "Content: Hello, World!" in output

def test_list_files(docker_container):
    """Test listing files through the prompt."""
    # Execute list command
    result = docker_container.exec_run(
        'python -c "print(\'list\\n\')" | python -m src.prompt_handler',
        tty=True
    )
    
    # Verify command output
    output = result.output.decode()
    assert "Contents of /app" in output
    assert "hello-world.txt" in output

def test_interactive_session():
    """Test full interactive session using pexpect."""
    # Start container with interactive session
    session = PopenSpawn('docker run -i --rm anthropic-agent:test')
    
    try:
        # Wait for prompt
        session.expect('(container)', timeout=5)
        
        # Create file
        session.sendline('create test.txt Test content')
        session.expect('Created file: /app/test.txt', timeout=5)
        
        # Verify file
        session.sendline('verify test.txt')
        session.expect('Content: Test content', timeout=5)
        
        # List files
        session.sendline('list')
        session.expect('test.txt', timeout=5)
        
        # Exit
        session.sendline('exit')
        session.expect(pexpect.EOF, timeout=5)
        
    finally:
        session.close()

def test_error_handling(docker_container):
    """Test error handling in the prompt."""
    # Test invalid command
    result = docker_container.exec_run(
        'python -c "print(\'invalid_command\\n\')" | python -m src.prompt_handler',
        tty=True
    )
    output = result.output.decode()
    assert "Unknown command: invalid_command" in output
    
    # Test missing filename
    result = docker_container.exec_run(
        'python -c "print(\'create\\n\')" | python -m src.prompt_handler',
        tty=True
    )
    output = result.output.decode()
    assert "Error: Filename required" in output

def test_logging(docker_container):
    """Test that operations are properly logged."""
    # Execute some commands
    docker_container.exec_run(
        'python -c "print(\'create log-test.txt Test logging\\n\')" | python -m src.prompt_handler',
        tty=True
    )
    
    # Check log file
    result = docker_container.exec_run('cat /app/logs/prompt.log')
    log_content = result.output.decode()
    
    assert "Created file: /app/log-test.txt" in log_content
    assert "[INFO]" in log_content 