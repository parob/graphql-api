"""
Pydantic Utilities

Helper functions for converting and handling Pydantic models in GraphQL arguments.
Separated from mapper.py to keep the mapper focused on type mapping.
"""

import inspect
from typing import Any, Dict, Optional, Tuple


def type_is_pydantic_model(type_: Any) -> bool:
    """
    Check if a type is a Pydantic model.

    Args:
        type_: The type to check

    Returns:
        True if it's a Pydantic BaseModel subclass
    """
    try:
        from pydantic import BaseModel
        return issubclass(type_, BaseModel)
    except (TypeError, ImportError):
        return False


def extract_list_type(param_type) -> Tuple[Optional[Any], Optional[Any]]:
    """
    Extract the inner type from a List or Optional[List] type annotation.

    Args:
        param_type: The type annotation to analyze

    Returns:
        Tuple of (list_type, item_type) or (None, None) if not a list
    """
    import typing_inspect

    # Handle Optional[List[T]]
    if typing_inspect.is_optional_type(param_type):
        args = typing_inspect.get_args(param_type, evaluate=True)
        for arg in args:
            if arg is not type(None):
                param_type = arg
                break

    # Check if it's a List type
    if typing_inspect.is_generic_type(param_type):
        origin = typing_inspect.get_origin(param_type)
        if origin is list:
            args = typing_inspect.get_args(param_type, evaluate=True)
            if args:
                return param_type, args[0]

    return None, None


def convert_dict_to_pydantic_model(input_dict: dict, model_class):
    """
    Convert a dictionary to a Pydantic model instance.

    Args:
        input_dict: Dictionary of values
        model_class: Pydantic model class to instantiate

    Returns:
        Instance of the Pydantic model

    Raises:
        ValueError: If validation fails
    """
    try:
        return model_class(**input_dict)
    except Exception as e:
        raise ValueError(f"Failed to convert dict to {model_class.__name__}: {e}")


def convert_pydantic_arguments(args_dict: Dict[str, Any], type_hints: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert dictionary arguments to Pydantic model instances where appropriate.

    This function examines the type hints and converts any dict arguments
    to their corresponding Pydantic model instances.

    Args:
        args_dict: Dictionary of argument name -> value
        type_hints: Dictionary of argument name -> type hint

    Returns:
        Dictionary with Pydantic models instantiated from dicts
    """
    converted_args = {}

    for arg_name, arg_value in args_dict.items():
        # Get the type hint for this argument
        param_type = type_hints.get(arg_name)

        if param_type is None:
            converted_args[arg_name] = arg_value
            continue

        # Check if this parameter is a Pydantic model
        if isinstance(arg_value, dict) and inspect.isclass(param_type) and type_is_pydantic_model(param_type):
            # Convert dict to Pydantic model instance
            try:
                converted_args[arg_name] = convert_dict_to_pydantic_model(arg_value, param_type)
            except (TypeError, ValueError, AttributeError):
                # If conversion fails due to validation or structure issues,
                # pass the original value and let normal error handling occur
                converted_args[arg_name] = arg_value

        # Check if this parameter is a List[PydanticModel] or Optional[List[PydanticModel]]
        elif isinstance(arg_value, list):
            list_type, list_item_type = extract_list_type(param_type)

            if list_type and list_item_type and inspect.isclass(list_item_type) and type_is_pydantic_model(list_item_type):
                # Convert each dict in the list to a Pydantic model instance
                try:
                    converted_args[arg_name] = [
                        convert_dict_to_pydantic_model(item, list_item_type)
                        if isinstance(item, dict)
                        else item
                        for item in arg_value
                    ]
                except (TypeError, ValueError, AttributeError):
                    # If conversion fails, pass the original value
                    converted_args[arg_name] = arg_value
            else:
                converted_args[arg_name] = arg_value
        else:
            converted_args[arg_name] = arg_value

    return converted_args
