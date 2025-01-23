"""Parser for handling Claude's tool call responses."""
from typing import Dict, Any, Optional, List, Union, Tuple
import json
import re
import logging
from dataclasses import dataclass
from .registry import ToolRegistry

logger = logging.getLogger(__name__)

@dataclass
class ToolCall:
    """Represents a parsed tool call from Claude's response."""
    tool_name: str
    parameters: Dict[str, Any]
    explanation: Optional[str] = None
    raw_text: Optional[str] = None

class ResponseParser:
    """Parser for extracting and validating tool calls from Claude's responses."""
    
    # Regex pattern for matching tool call blocks
    TOOL_CALL_PATTERN = re.compile(
        r'<function_calls>\s*'
        r'<invoke name="([^"]+)">\s*'
        r'((?:<parameter name="[^"]+">.*?</parameter>\s*)*)'
        r'</invoke>\s*'
        r'</function_calls>',
        re.DOTALL
    )
    
    # Pattern for matching individual parameters
    PARAMETER_PATTERN = re.compile(
        r'<parameter name="([^"]+)">(.*?)</parameter>',
        re.DOTALL
    )
    
    def __init__(self, registry: ToolRegistry):
        """
        Initialize the response parser.
        
        Args:
            registry: Tool registry for validating tool calls
        """
        self._registry = registry
        
    def parse_response(self, response: str) -> List[ToolCall]:
        """
        Parse tool calls from Claude's response.
        
        Args:
            response: Raw response text from Claude
            
        Returns:
            List[ToolCall]: List of parsed tool calls
            
        Raises:
            ValueError: If response contains invalid tool calls
        """
        tool_calls = []
        
        # Find all tool call blocks
        for match in self.TOOL_CALL_PATTERN.finditer(response):
            tool_name = match.group(1)
            params_text = match.group(2)
            raw_text = match.group(0)
            
            # Extract explanation from preceding text
            explanation = self._extract_explanation(response, match.start())
            
            # Parse parameters
            parameters = {}
            for param_match in self.PARAMETER_PATTERN.finditer(params_text):
                param_name = param_match.group(1)
                param_value = param_match.group(2).strip()
                
                # Handle JSON values
                try:
                    if param_value.startswith('{') or param_value.startswith('['):
                        param_value = json.loads(param_value)
                except json.JSONDecodeError:
                    pass
                    
                parameters[param_name] = param_value
            
            # Validate tool call
            self._validate_tool_call(tool_name, parameters)
            
            tool_calls.append(ToolCall(
                tool_name=tool_name,
                parameters=parameters,
                explanation=explanation,
                raw_text=raw_text
            ))
            
        return tool_calls
    
    def _extract_explanation(self, response: str, tool_call_start: int) -> Optional[str]:
        """Extract explanation from text preceding tool call."""
        # Look for explanation in previous paragraph
        text_before = response[:tool_call_start].strip()
        paragraphs = text_before.split('\n\n')
        
        if paragraphs:
            last_para = paragraphs[-1].strip()
            if last_para:
                return last_para
        return None
    
    def _validate_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> None:
        """
        Validate a tool call against the registry.
        
        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            
        Raises:
            ValueError: If tool call is invalid
        """
        # Check if tool exists
        tool = self._registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        # Validate parameters against schema
        schema = tool.parameters
        try:
            self._registry._validator.validate_parameters(schema, parameters)
        except Exception as e:
            raise ValueError(f"Invalid parameters for {tool_name}: {str(e)}")
    
    def format_result(self, result: Any, tool_name: str) -> str:
        """
        Format a tool execution result for Claude's consumption.
        
        Args:
            result: Tool execution result
            tool_name: Name of the tool that produced the result
            
        Returns:
            str: Formatted result string
        """
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2)
        return str(result) 