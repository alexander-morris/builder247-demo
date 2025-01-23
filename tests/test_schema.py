"""Tests for schema validation functionality."""
import pytest
from src.tools.schema import SchemaValidator

def test_parameter_validation():
    """Test parameter validation against schema."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "age": {"type": "integer", "minimum": 0}
        },
        "required": ["name"]
    }
    
    # Valid parameters
    valid_params = {"name": "test", "age": 25}
    assert SchemaValidator.validate_parameters(schema, valid_params) is None
    
    # Missing required field
    invalid_params = {"age": 25}
    errors = SchemaValidator.validate_parameters(schema, invalid_params)
    assert errors is not None
    assert any("name" in error for error in errors)
    
    # Wrong type
    invalid_params = {"name": "test", "age": "25"}
    errors = SchemaValidator.validate_parameters(schema, invalid_params)
    assert errors is not None
    assert any("age" in error for error in errors)

def test_tool_schema_validation():
    """Test tool schema validation."""
    # Valid schema
    valid_schema = {
        "name": "test_tool",
        "description": "A test tool",
        "version": "1.0.0",
        "parameters": {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        },
        "returns": {
            "type": "object",
            "properties": {
                "output": {"type": "string"}
            }
        }
    }
    assert SchemaValidator.validate_tool_schema(valid_schema) is None
    
    # Missing required fields
    invalid_schema = {
        "name": "test_tool",
        "description": "A test tool"
    }
    errors = SchemaValidator.validate_tool_schema(invalid_schema)
    assert errors is not None
    assert len(errors) == 3  # missing version, parameters, returns
    
    # Invalid parameters schema
    invalid_schema = valid_schema.copy()
    invalid_schema["parameters"] = {"type": "invalid"}
    errors = SchemaValidator.validate_tool_schema(invalid_schema)
    assert errors is not None
    assert any("parameters" in error for error in errors)

def test_example_validation():
    """Test example validation against schema."""
    schema = {
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "minLength": 1}
            },
            "required": ["text"]
        },
        "returns": {
            "type": "object",
            "properties": {
                "length": {"type": "integer", "minimum": 0}
            },
            "required": ["length"]
        }
    }
    
    # Valid example
    valid_example = {
        "input": {"text": "hello"},
        "output": {"length": 5}
    }
    assert SchemaValidator.validate_example(schema, valid_example) is None
    
    # Invalid input
    invalid_example = {
        "input": {"text": ""},
        "output": {"length": 0}
    }
    errors = SchemaValidator.validate_example(schema, invalid_example)
    assert errors is not None
    assert any("text" in error for error in errors)
    
    # Invalid output
    invalid_example = {
        "input": {"text": "hello"},
        "output": {"length": -1}
    }
    errors = SchemaValidator.validate_example(schema, invalid_example)
    assert errors is not None
    assert any("length" in error for error in errors) 