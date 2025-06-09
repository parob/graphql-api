import inspect
import typing

from typing import Any, Type, cast

from graphql import GraphQLField, GraphQLObjectType, GraphQLOutputType
from graphql.type.definition import is_output_type
from pydantic import BaseModel

from graphql_api.utils import to_camel_case

if typing.TYPE_CHECKING:
    from graphql_api.mapper import GraphQLTypeMapper


def type_is_pydantic_model(type_: Any) -> bool:
    try:
        return issubclass(type_, BaseModel)
    except TypeError:
        return False


def type_from_pydantic_model(
    pydantic_model: Type[BaseModel], mapper: "GraphQLTypeMapper"
) -> GraphQLObjectType:
    def get_fields() -> dict[str, GraphQLField]:
        fields = {}

        model_fields = getattr(pydantic_model, "model_fields", {})
        for name, field in model_fields.items():
            field_type = field.annotation
            graphql_type = mapper.map(field_type)
            if graphql_type is None:
                raise TypeError(f"Unable to map pydantic field '{name}' with type {field_type}")
            if not is_output_type(graphql_type):
                raise TypeError(
                    f"Mapped type for pydantic field '{name}' is not a valid GraphQL Output Type."
                )

            def create_resolver(_name):
                def resolver(instance, info):
                    return getattr(instance, _name)
                return resolver

            fields[to_camel_case(name)] = GraphQLField(
                cast(GraphQLOutputType, graphql_type),
                resolve=create_resolver(name)
            )
        return fields

    return GraphQLObjectType(
        name=pydantic_model.__name__,
        fields=get_fields,
        description=inspect.getdoc(pydantic_model),
    )
