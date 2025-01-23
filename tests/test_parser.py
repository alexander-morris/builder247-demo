"""Tests for response parser functionality."""
import pytest
from typing import Dict, Any
from src.tools.registry import ToolRegistry
from src.tools.parser import ResponseParser, ToolCall

@pytest.fixture
def registry():
    """Create a test tool registry."""
    registry = ToolRegistry()
    
    @registry.register(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer", "minimum": 0}
            },
            "required": ["text"]
        }
    )
    def test_tool(text: str, count: int = 1) -> Dict[str, Any]:
        return {"result": text * count}
    
    return registry

@pytest.fixture
def parser(registry):
    """Create a test response parser."""
    return ResponseParser(registry)

def test_parse_simple_tool_call(parser):
    """Test parsing a simple tool call."""
    response = '''
I will use the test tool to process the text.

<function_calls>
<invoke name="test_tool">
<parameter name="text">hello</parameter>
<parameter name="count">3</parameter>
</invoke>
</function_calls>
'''
    
    tool_calls = parser.parse_response(response)
    assert len(tool_calls) == 1
    
    call = tool_calls[0]
    assert isinstance(call, ToolCall)
    assert call.tool_name == "test_tool"
    assert call.parameters == {"text": "hello", "count": "3"}
    assert "use the test tool" in call.explanation
    assert "<function_calls>" in call.raw_text

def test_parse_json_parameters(parser):
    """Test parsing parameters with JSON values."""
    response = '''
<function_calls>
<invoke name="test_tool">
<parameter name="text">hello</parameter>
<parameter name="options">{"repeat": true, "case": "upper"}</parameter>
</invoke>
</function_calls>
'''
    
    tool_calls = parser.parse_response(response)
    assert len(tool_calls) == 1
    
    call = tool_calls[0]
    assert call.parameters["text"] == "hello"
    assert isinstance(call.parameters["options"], dict)
    assert call.parameters["options"] == {"repeat": True, "case": "upper"}

def test_parse_multiple_tool_calls(parser):
    """Test parsing multiple tool calls."""
    response = '''
First tool call:
<function_calls>
<invoke name="test_tool">
<parameter name="text">hello</parameter>
</invoke>
</function_calls>

Second tool call:
<function_calls>
<invoke name="test_tool">
<parameter name="text">world</parameter>
<parameter name="count">2</parameter>
</invoke>
</function_calls>
'''
    
    tool_calls = parser.parse_response(response)
    assert len(tool_calls) == 2
    
    assert tool_calls[0].parameters == {"text": "hello"}
    assert "First tool call" in tool_calls[0].explanation
    
    assert tool_calls[1].parameters == {"text": "world", "count": "2"}
    assert "Second tool call" in tool_calls[1].explanation

def test_validate_unknown_tool(parser):
    """Test validation of unknown tool."""
    response = '''
<function_calls>
<invoke name="unknown_tool">
<parameter name="text">hello</parameter>
</invoke>
</function_calls>
'''
    
    with pytest.raises(ValueError) as exc_info:
        parser.parse_response(response)
    assert "Unknown tool" in str(exc_info.value)

def test_validate_invalid_parameters(parser):
    """Test validation of invalid parameters."""
    response = '''
<function_calls>
<invoke name="test_tool">
<parameter name="count">-1</parameter>
</invoke>
</function_calls>
'''
    
    with pytest.raises(ValueError) as exc_info:
        parser.parse_response(response)
    assert "Invalid parameters" in str(exc_info.value)

def test_format_result(parser):
    """Test result formatting."""
    # Dictionary result
    dict_result = {"key": "value", "numbers": [1, 2, 3]}
    formatted = parser.format_result(dict_result, "test_tool")
    assert isinstance(formatted, str)
    assert "key" in formatted
    assert "[1, 2, 3]" in formatted
    
    # Simple result
    simple_result = "hello world"
    formatted = parser.format_result(simple_result, "test_tool")
    assert formatted == "hello world"

def test_malformed_tool_calls(parser):
    """Test handling of malformed tool calls."""
    # Missing parameter name
    response = '''
<function_calls>
<invoke name="test_tool">
<parameter>hello</parameter>
</invoke>
</function_calls>
'''
    tool_calls = parser.parse_response(response)
    assert len(tool_calls) == 0
    
    # Invalid XML
    response = '''
<function_calls>
<invoke name="test_tool">
<parameter name="text">hello
</invoke>
</function_calls>
'''
    tool_calls = parser.parse_response(response)
    assert len(tool_calls) == 0 