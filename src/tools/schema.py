"""Schema validation utilities for tool registry."""
from typing import Dict, Any, Optional, List
import jsonschema
from jsonschema import validate, ValidationError
import logging

logger = logging.getLogger(__name__)

class SchemaValidator:
    """Validator for tool schemas and parameters."""
    
    @staticmethod
    def validate_parameters(schema: Dict[str, Any], parameters: Dict[str, Any]) -> Optional[List[str]]:
        """
        Validate parameters against a schema.
        
        Args:
            schema: JSONSchema for parameters
            parameters: Parameter values to validate
            
        Returns:
            Optional[List[str]]: List of validation errors if any, None if valid
        """
        try:
            validate(instance=parameters, schema=schema)
            return None
        except ValidationError as e:
            logger.error(f"Parameter validation error: {str(e)}")
            return [str(e)]

    @staticmethod
    def validate_tool_schema(schema: Dict[str, Any]) -> Optional[List[str]]:
        """
        Validate a tool schema definition.
        
        Args:
            schema: Tool schema to validate
            
        Returns:
            Optional[List[str]]: List of validation errors if any, None if valid
        """
        required_fields = ["name", "description", "version", "parameters", "returns"]
        errors = []
        
        # Check required fields
        for field in required_fields:
            if field not in schema:
                errors.append(f"Missing required field: {field}")
        
        # Validate parameters schema
        if "parameters" in schema:
            try:
                jsonschema.validators.validator_for(schema["parameters"]).check_schema(schema["parameters"])
            except jsonschema.exceptions.SchemaError as e:
                errors.append(f"Invalid parameters schema: {str(e)}")
        
        # Validate returns schema
        if "returns" in schema:
            try:
                jsonschema.validators.validator_for(schema["returns"]).check_schema(schema["returns"])
            except jsonschema.exceptions.SchemaError as e:
                errors.append(f"Invalid returns schema: {str(e)}")
                
        return errors if errors else None

    @staticmethod
    def validate_example(schema: Dict[str, Any], example: Dict[str, Any]) -> Optional[List[str]]:
        """
        Validate an example against parameter and return schemas.
        
        Args:
            schema: Tool schema containing parameter and return definitions
            example: Example to validate
            
        Returns:
            Optional[List[str]]: List of validation errors if any, None if valid
        """
        errors = []
        
        # Validate input parameters
        if "input" in example:
            param_errors = SchemaValidator.validate_parameters(schema["parameters"], example["input"])
            if param_errors:
                errors.extend([f"Input validation error: {e}" for e in param_errors])
        
        # Validate output
        if "output" in example:
            try:
                validate(instance=example["output"], schema=schema["returns"])
            except ValidationError as e:
                errors.append(f"Output validation error: {str(e)}")
                
        return errors if errors else None 