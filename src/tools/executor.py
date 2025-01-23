"""Tool execution pipeline for managing tool invocations."""
from typing import Dict, Any, Optional, List, Union
import asyncio
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from .registry import ToolRegistry

logger = logging.getLogger(__name__)

@dataclass
class ExecutionResult:
    """Result of a tool execution."""
    tool_name: str
    status: str  # 'success', 'error', 'timeout'
    result: Optional[Any]
    error: Optional[str]
    start_time: datetime
    end_time: datetime
    duration: float  # in seconds
    metadata: Dict[str, Any]

class ToolExecutor:
    """Executor for managing tool invocations."""
    
    def __init__(self, registry: ToolRegistry, default_timeout: float = 30.0):
        """
        Initialize the tool executor.
        
        Args:
            registry: Tool registry containing available tools
            default_timeout: Default timeout in seconds for tool execution
        """
        self._registry = registry
        self._default_timeout = default_timeout
        self._active_executions: Dict[str, asyncio.Task] = {}
        
    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute a tool asynchronously.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            timeout: Optional timeout in seconds
            metadata: Optional metadata to include in result
            
        Returns:
            ExecutionResult: Result of the execution
            
        Raises:
            ValueError: If tool not found or parameters invalid
        """
        start_time = datetime.now()
        timeout = timeout or self._default_timeout
        metadata = metadata or {}
        
        try:
            # Get tool and validate parameters
            tool = self._registry.get_tool(tool_name)
            if not tool:
                raise ValueError(f"Tool not found: {tool_name}")
            
            # Create execution task
            task = asyncio.create_task(self._execute_tool(tool_name, parameters))
            self._active_executions[tool_name] = task
            
            try:
                # Wait for result with timeout
                result = await asyncio.wait_for(task, timeout=timeout)
                status = "success"
                error = None
            except asyncio.TimeoutError:
                status = "timeout"
                error = f"Tool execution timed out after {timeout} seconds"
                result = None
                # Cancel the task
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
        except Exception as e:
            status = "error"
            error = str(e)
            result = None
            logger.error(f"Error executing {tool_name}: {error}")
            
        finally:
            # Clean up
            self._active_executions.pop(tool_name, None)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Log execution
            logger.info(
                f"Tool execution completed: {tool_name}",
                extra={
                    "tool": tool_name,
                    "status": status,
                    "duration": duration,
                    "metadata": metadata
                }
            )
            
        return ExecutionResult(
            tool_name=tool_name,
            status=status,
            result=result,
            error=error,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            metadata=metadata
        )
    
    async def _execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a tool in a separate thread to avoid blocking."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._registry.execute,
            tool_name,
            parameters
        )
    
    def cancel_execution(self, tool_name: str) -> bool:
        """
        Cancel an active tool execution.
        
        Args:
            tool_name: Name of the tool to cancel
            
        Returns:
            bool: True if execution was cancelled, False if not found
        """
        task = self._active_executions.get(tool_name)
        if task and not task.done():
            task.cancel()
            return True
        return False
    
    def get_active_executions(self) -> List[str]:
        """Get list of currently executing tools."""
        return [
            name for name, task in self._active_executions.items()
            if not task.done()
        ] 