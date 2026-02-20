import inspect
import typing

from typing import Any, Type, cast, Optional

from graphql import GraphQLField, GraphQLObjectType, GraphQLOutputType, GraphQLInputField, GraphQLInputObjectType, GraphQLInputType
from graphql.type.definition import is_output_type, is_input_type
from pydantic import BaseModel

from graphql_api.utils import to_camel_case, to_snake_case

if typing.TYPE_CHECKING:
    from graphql_api.mapper import GraphQLTypeMapper


def type_is_pydantic_model(type_: Any) -> bool:
    try:
        return issubclass(type_, BaseModel)
    except TypeError:
        return False


def _get_pydantic_model_description(pydantic_model: Type[BaseModel], max_docstring_length: Optional[int] = None) -> str:
    """
    Get description for a Pydantic model, filtering out default BaseModel docstring.

    Args:
        pydantic_model: The Pydantic model to get the description for
        max_docstring_length: Optional maximum length for docstrings (truncates if longer)

    Returns None if the model has no explicit docstring or uses the default BaseModel docstring.
    """
    doc = inspect.getdoc(pydantic_model)

    # If no docstring, return None
    if not doc:
        return None

    # Get the default BaseModel docstring to compare against
    default_doc = inspect.getdoc(BaseModel)

    # If it's the default BaseModel docstring, return None
    if doc == default_doc:
        return None

    # Apply truncation if requested
    if max_docstring_length is not None and len(doc) > max_docstring_length:
        doc = doc[:max_docstring_length].rstrip() + "..."

    return doc


def type_from_pydantic_model(
    pydantic_model: Type[BaseModel], mapper: "GraphQLTypeMapper"
) -> GraphQLObjectType | GraphQLInputObjectType:
    model_fields = getattr(pydantic_model, "model_fields", {})

    if mapper.as_input:
        # Create input type
        def get_input_fields() -> dict[str, GraphQLInputField]:
            fields = {}

            for name, field in model_fields.items():
                field_type = field.annotation
                graphql_type = mapper.map(field_type)
                if graphql_type is None:
                    raise TypeError(
                        f"Unable to map pydantic field '{name}' with type {field_type}"
                    )
                if not is_input_type(graphql_type):
                    raise TypeError(
                        f"Mapped type for pydantic field '{name}' is not a valid GraphQL Input Type."
                    )

                fields[to_camel_case(name)] = GraphQLInputField(
                    cast(GraphQLInputType, graphql_type)
                )
            return fields

        def _make_out_type(model_cls: Type[BaseModel]):
            """Create an out_type that converts GraphQL input dicts to Pydantic models.

            Mirrors the pattern in mapper.py's map_to_input for dataclass types.
            """
            def out_type(data):
                # Convert camelCase GraphQL keys to snake_case Python keys
                converted = {to_snake_case(key): value for key, value in data.items()}
                # Strip None values so Pydantic uses its field defaults
                # (graphql-core sets None for nullable fields not provided in input)
                fields_with_defaults = {
                    name for name, info in model_cls.model_fields.items()
                    if info.default is not None or info.default_factory is not None
                }
                converted = {
                    k: v for k, v in converted.items()
                    if v is not None or k not in fields_with_defaults
                }
                return model_cls(**converted)
            return out_type

        return GraphQLInputObjectType(
            name=f"{pydantic_model.__name__}Input",
            fields=get_input_fields,
            out_type=_make_out_type(pydantic_model),
            description=_get_pydantic_model_description(
                pydantic_model, mapper.max_docstring_length),
        )
    else:
        # Create output type
        def get_fields() -> dict[str, GraphQLField]:
            fields = {}

            for name, field in model_fields.items():
                field_type = field.annotation
                graphql_type = mapper.map(field_type)
                if graphql_type is None:
                    raise TypeError(
                        f"Unable to map pydantic field '{name}' with type {field_type}"
                    )
                if not is_output_type(graphql_type):
                    raise TypeError(
                        f"Mapped type for pydantic field '{name}' is not a valid GraphQL Output Type."
                    )

                def create_resolver(_name):
                    def resolver(instance, info):
                        return getattr(instance, _name)

                    return resolver

                fields[to_camel_case(name)] = GraphQLField(
                    cast(GraphQLOutputType, graphql_type), resolve=create_resolver(name)
                )
            return fields

        return GraphQLObjectType(
            name=pydantic_model.__name__,
            fields=get_fields,
            description=_get_pydantic_model_description(
                pydantic_model, mapper.max_docstring_length),
        )
