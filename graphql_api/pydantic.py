import inspect
import typing

from typing import Any, Type, cast, Optional

from graphql import GraphQLField, GraphQLObjectType, GraphQLOutputType, GraphQLInputField, GraphQLInputObjectType, GraphQLInputType
from graphql.type.definition import is_output_type, is_input_type
from pydantic import BaseModel

from graphql_api.utils import to_camel_case

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

        return GraphQLInputObjectType(
            name=f"{pydantic_model.__name__}Input",
            fields=get_input_fields,
            description=_get_pydantic_model_description(pydantic_model, mapper.max_docstring_length),
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
            description=_get_pydantic_model_description(pydantic_model, mapper.max_docstring_length),
        )
