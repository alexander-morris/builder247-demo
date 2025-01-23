"""Tool registry system for managing available tools."""
from typing import Dict, Any, Optional, Callable, List
import json
import inspect
from dataclasses import dataclass
from pathlib import Path
import logging
from .schema import SchemaValidator

logger = logging.getLogger(__name__)

@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""
    name: str
    description: str
    version: str
    parameters: Dict[str, Any]
    returns: Dict[str, Any]
    examples: List[Dict[str, Any]]
    function: Callable

class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, ToolMetadata] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._validator = SchemaValidator()
        
    def register(
        self,
        name: str,
        description: str,
        version: str = "1.0.0",
        parameters: Optional[Dict[str, Any]] = None,
        returns: Optional[Dict[str, Any]] = None,
        examples: Optional[List[Dict[str, Any]]] = None
    ) -> Callable:
        """
        Decorator to register a tool function.
        
        Args:
            name: Tool name
            description: Tool description
            version: Tool version
            parameters: JSONSchema for parameters
            returns: JSONSchema for return value
            examples: List of usage examples
            
        Returns:
            Callable: Decorator function
        """
        def decorator(func: Callable) -> Callable:
            # Extract parameter info from function signature
            sig = inspect.signature(func)
            if parameters is None:
                param_schema = {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
                for param_name, param in sig.parameters.items():
                    if param.annotation != inspect.Parameter.empty:
                        param_schema["properties"][param_name] = {
                            "type": self._get_type_name(param.annotation)
                        }
                    if param.default == inspect.Parameter.empty:
                        param_schema["required"].append(param_name)
            else:
                param_schema = parameters
                
            # Create return schema if not provided
            return_schema = returns or {
                "type": "object",
                "properties": {
                    "result": {
                        "type": self._get_type_name(sig.return_annotation)
                    }
                }
            }
            
            # Create tool schema
            tool_schema = {
                "name": name,
                "description": description,
                "version": version,
                "parameters": param_schema,
                "returns": return_schema,
                "examples": examples or []
            }
            
            # Validate schema
            errors = self._validator.validate_tool_schema(tool_schema)
            if errors:
                error_msg = "\n".join(errors)
                logger.error(f"Invalid tool schema for {name}:\n{error_msg}")
                raise ValueError(f"Invalid tool schema: {error_msg}")
            
            # Validate examples if provided
            if examples:
                for i, example in enumerate(examples):
                    errors = self._validator.validate_example(tool_schema, example)
                    if errors:
                        error_msg = "\n".join(errors)
                        logger.error(f"Invalid example {i} for {name}:\n{error_msg}")
                        raise ValueError(f"Invalid example {i}: {error_msg}")
            
            # Register the tool
            tool_metadata = ToolMetadata(
                name=name,
                description=description,
                version=version,
                parameters=param_schema,
                returns=return_schema,
                examples=examples or [],
                function=func
            )
            self._tools[name] = tool_metadata
            self._schemas[name] = tool_schema
            
            logger.info(f"Registered tool: {name} v{version}")
            return func
            
        return decorator
    
    def execute(self, name: str, parameters: Dict[str, Any]) -> Any:
        """
        Execute a registered tool.
        
        Args:
            name: Tool name
            parameters: Tool parameters
            
        Returns:
            Any: Tool execution result
            
        Raises:
            ValueError: If tool not found or parameters invalid
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
            
        # Validate parameters
        errors = self._validator.validate_parameters(tool.parameters, parameters)
        if errors:
            error_msg = "\n".join(errors)
            logger.error(f"Invalid parameters for {name}:\n{error_msg}")
            raise ValueError(f"Invalid parameters: {error_msg}")
            
        # Execute tool
        try:
            result = tool.function(**parameters)
            
            # Validate result
            if isinstance(result, dict):
                errors = self._validator.validate_parameters(tool.returns, result)
                if errors:
                    error_msg = "\n".join(errors)
                    logger.error(f"Invalid result from {name}:\n{error_msg}")
                    raise ValueError(f"Invalid result: {error_msg}")
                    
            return result
            
        except Exception as e:
            logger.error(f"Error executing {name}: {str(e)}")
            raise
    
    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """Get a registered tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get JSONSchema for a tool."""
        return self._schemas.get(name)
    
    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get JSONSchema for all tools."""
        return self._schemas.copy()
    
    def save_schemas(self, path: Path) -> None:
        """Save tool schemas to a file."""
        with open(path, 'w') as f:
            json.dump(self._schemas, f, indent=2)
    
    def load_schemas(self, path: Path) -> None:
        """Load tool schemas from a file."""
        with open(path) as f:
            schemas = json.load(f)
            
        # Validate all schemas before loading
        for name, schema in schemas.items():
            errors = self._validator.validate_tool_schema(schema)
            if errors:
                error_msg = "\n".join(errors)
                logger.error(f"Invalid schema for {name}:\n{error_msg}")
                raise ValueError(f"Invalid schema for {name}: {error_msg}")
                
        self._schemas = schemas
    
    @staticmethod
    def _get_type_name(type_hint: Any) -> str:
        """Convert Python type hint to JSONSchema type."""
        type_map = {
            str: "string",
            int: "integer", 
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            None: "null"
        }
        return type_map.get(type_hint, "string") 