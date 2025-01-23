"""Tests for tool executor functionality."""
import pytest
import asyncio
import time
from datetime import datetime
from typing import Dict, Any
from src.tools.registry import ToolRegistry
from src.tools.executor import ToolExecutor, ExecutionResult

@pytest.fixture
def registry():
    """Create a test tool registry."""
    return ToolRegistry()

@pytest.fixture
def executor(registry):
    """Create a test tool executor."""
    return ToolExecutor(registry)

@pytest.mark.asyncio
async def test_successful_execution(registry, executor):
    """Test successful tool execution."""
    @registry.register(
        name="test_tool",
        description="A test tool"
    )
    def test_tool(value: str) -> Dict[str, str]:
        return {"result": value.upper()}
    
    result = await executor.execute("test_tool", {"value": "hello"})
    
    assert isinstance(result, ExecutionResult)
    assert result.tool_name == "test_tool"
    assert result.status == "success"
    assert result.result == {"result": "HELLO"}
    assert result.error is None
    assert isinstance(result.start_time, datetime)
    assert isinstance(result.end_time, datetime)
    assert result.duration >= 0
    assert result.metadata == {}

@pytest.mark.asyncio
async def test_execution_error(registry, executor):
    """Test tool execution with error."""
    @registry.register(
        name="error_tool",
        description="A tool that raises an error"
    )
    def error_tool():
        raise ValueError("Test error")
    
    result = await executor.execute("error_tool", {})
    
    assert result.status == "error"
    assert result.result is None
    assert "Test error" in result.error
    assert result.duration >= 0

@pytest.mark.asyncio
async def test_execution_timeout(registry, executor):
    """Test tool execution timeout."""
    @registry.register(
        name="slow_tool",
        description="A slow tool"
    )
    def slow_tool():
        time.sleep(0.5)  # Simulate slow operation
        return "done"
    
    result = await executor.execute("slow_tool", {}, timeout=0.1)
    
    assert result.status == "timeout"
    assert result.result is None
    assert "timed out" in result.error
    assert result.duration >= 0.1

@pytest.mark.asyncio
async def test_invalid_tool(executor):
    """Test execution with non-existent tool."""
    result = await executor.execute("nonexistent", {})
    
    assert result.status == "error"
    assert result.result is None
    assert "not found" in result.error

@pytest.mark.asyncio
async def test_cancel_execution(registry, executor):
    """Test cancelling tool execution."""
    @registry.register(
        name="cancellable_tool",
        description="A tool that can be cancelled"
    )
    def cancellable_tool():
        time.sleep(1)  # Long operation
        return "done"
    
    # Start execution in background
    task = asyncio.create_task(
        executor.execute("cancellable_tool", {})
    )
    
    # Wait a bit and cancel
    await asyncio.sleep(0.1)
    cancelled = executor.cancel_execution("cancellable_tool")
    assert cancelled is True
    
    # Verify execution was cancelled
    result = await task
    assert result.status == "error"
    assert "cancelled" in result.error.lower()

@pytest.mark.asyncio
async def test_active_executions(registry, executor):
    """Test tracking active executions."""
    @registry.register(
        name="active_tool",
        description="A tool that runs for a while"
    )
    def active_tool():
        time.sleep(0.2)
        return "done"
    
    # Start execution
    task = asyncio.create_task(
        executor.execute("active_tool", {})
    )
    
    # Check active executions
    await asyncio.sleep(0.1)
    active = executor.get_active_executions()
    assert "active_tool" in active
    
    # Wait for completion
    await task
    active = executor.get_active_executions()
    assert len(active) == 0

@pytest.mark.asyncio
async def test_execution_with_metadata(registry, executor):
    """Test execution with metadata."""
    @registry.register(
        name="meta_tool",
        description="A tool with metadata"
    )
    def meta_tool() -> str:
        return "done"
    
    metadata = {
        "user": "test_user",
        "request_id": "123",
        "priority": "high"
    }
    
    result = await executor.execute(
        "meta_tool",
        {},
        metadata=metadata
    )
    
    assert result.metadata == metadata 