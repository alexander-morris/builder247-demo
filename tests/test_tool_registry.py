"""Tests for tool registry functionality."""
import pytest
from pathlib import Path
from typing import Dict, Any, List
from src.tools.registry import ToolRegistry, ToolMetadata

@pytest.fixture
def registry():
    """Create a test tool registry."""
    return ToolRegistry()

def test_tool_registration(registry):
    """Test basic tool registration."""
    @registry.register(
        name="test_tool",
        description="A test tool",
        version="1.0.0"
    )
    def test_tool(arg1: str, arg2: int = 0) -> Dict[str, Any]:
        return {"result": f"{arg1} {arg2}"}
    
    # Verify tool is registered
    assert "test_tool" in registry.list_tools()
    
    # Verify metadata
    tool = registry.get_tool("test_tool")
    assert isinstance(tool, ToolMetadata)
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.version == "1.0.0"
    
    # Verify schema generation
    schema = registry.get_schema("test_tool")
    assert schema["parameters"]["type"] == "object"
    assert "arg1" in schema["parameters"]["properties"]
    assert "arg2" in schema["parameters"]["properties"]
    assert schema["parameters"]["properties"]["arg1"]["type"] == "string"
    assert schema["parameters"]["properties"]["arg2"]["type"] == "integer"
    assert "arg1" in schema["parameters"]["required"]
    assert "arg2" not in schema["parameters"]["required"]

def test_custom_schema(registry):
    """Test registration with custom schema."""
    custom_params = {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "Input value",
                "minLength": 1
            }
        },
        "required": ["input"]
    }
    
    custom_returns = {
        "type": "object",
        "properties": {
            "output": {
                "type": "string",
                "description": "Processed output"
            }
        }
    }
    
    @registry.register(
        name="custom_tool",
        description="Tool with custom schema",
        parameters=custom_params,
        returns=custom_returns,
        examples=[{"input": {"input": "test"}, "output": {"output": "TEST"}}]
    )
    def custom_tool(input: str) -> Dict[str, str]:
        return {"output": input.upper()}
    
    # Verify custom schema
    schema = registry.get_schema("custom_tool")
    assert schema["parameters"] == custom_params
    assert schema["returns"] == custom_returns
    assert len(schema["examples"]) == 1

def test_schema_persistence(registry, tmp_path):
    """Test saving and loading schemas."""
    @registry.register(
        name="persist_tool",
        description="Tool for testing persistence"
    )
    def persist_tool(value: str) -> str:
        return value.upper()
    
    # Save schemas
    schema_file = tmp_path / "schemas.json"
    registry.save_schemas(schema_file)
    
    # Create new registry and load schemas
    new_registry = ToolRegistry()
    new_registry.load_schemas(schema_file)
    
    # Verify schemas match
    assert registry.get_all_schemas() == new_registry.get_all_schemas()

def test_tool_listing_and_retrieval(registry):
    """Test tool listing and retrieval."""
    # Register multiple tools
    @registry.register(name="tool1", description="First tool")
    def tool1(): pass
    
    @registry.register(name="tool2", description="Second tool")
    def tool2(): pass
    
    # Test listing
    tools = registry.list_tools()
    assert len(tools) == 2
    assert "tool1" in tools
    assert "tool2" in tools
    
    # Test retrieval
    tool1_meta = registry.get_tool("tool1")
    assert tool1_meta.description == "First tool"
    
    # Test non-existent tool
    assert registry.get_tool("nonexistent") is None
    assert registry.get_schema("nonexistent") is None

def test_tool_versioning(registry):
    """Test tool versioning."""
    @registry.register(
        name="versioned_tool",
        description="Tool with version",
        version="2.1.0"
    )
    def versioned_tool(): pass
    
    tool = registry.get_tool("versioned_tool")
    assert tool.version == "2.1.0"
    
    schema = registry.get_schema("versioned_tool")
    assert schema["version"] == "2.1.0"

def test_tool_execution(registry):
    """Test tool execution with validation."""
    @registry.register(
        name="math_tool",
        description="Math operations",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "number", "minimum": 0},
                "y": {"type": "number", "minimum": 0}
            },
            "required": ["x", "y"]
        },
        returns={
            "type": "object",
            "properties": {
                "sum": {"type": "number"},
                "product": {"type": "number"}
            },
            "required": ["sum", "product"]
        }
    )
    def math_tool(x: float, y: float) -> Dict[str, float]:
        return {"sum": x + y, "product": x * y}
    
    # Test valid execution
    result = registry.execute("math_tool", {"x": 2, "y": 3})
    assert result == {"sum": 5, "product": 6}
    
    # Test invalid parameters
    with pytest.raises(ValueError) as exc_info:
        registry.execute("math_tool", {"x": -1, "y": 3})
    assert "minimum" in str(exc_info.value)
    
    # Test missing parameters
    with pytest.raises(ValueError) as exc_info:
        registry.execute("math_tool", {"x": 2})
    assert "required" in str(exc_info.value)
    
    # Test non-existent tool
    with pytest.raises(ValueError) as exc_info:
        registry.execute("nonexistent", {})
    assert "not found" in str(exc_info.value)

def test_invalid_schema_registration(registry):
    """Test registration with invalid schema."""
    # Invalid parameter type
    with pytest.raises(ValueError) as exc_info:
        @registry.register(
            name="invalid_tool",
            description="Tool with invalid schema",
            parameters={"type": "invalid"}
        )
        def invalid_tool(): pass
    assert "Invalid tool schema" in str(exc_info.value)
    
    # Invalid example
    with pytest.raises(ValueError) as exc_info:
        @registry.register(
            name="example_tool",
            description="Tool with invalid example",
            parameters={
                "type": "object",
                "properties": {"input": {"type": "string"}}
            },
            examples=[{"input": {"input": 123}}]  # Wrong type
        )
        def example_tool(input: str): pass
    assert "Invalid example" in str(exc_info.value) 