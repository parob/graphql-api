import inspect
import typing
from typing import Any, Type, cast

from graphql import GraphQLField, GraphQLObjectType, GraphQLNonNull, GraphQLList
import graphql # Added import
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
    model_name = pydantic_model.__name__
    model_description = inspect.cleandoc(pydantic_model.__doc__) if pydantic_model.__doc__ else None

    graphql_fields = {}
    for field_name, field_info in pydantic_model.model_fields.items():
        python_type_hint = field_info.annotation

        origin = typing.get_origin(python_type_hint)
        args = typing.get_args(python_type_hint)

        is_outer_optional = origin is typing.Union and type(None) in args

        if is_outer_optional:
            effective_type_to_map = next(arg for arg in args if arg is not type(None))
        else:
            effective_type_to_map = python_type_hint

        # Renamed mapped_graphql_type to mapped_type_for_field_content for clarity
        mapped_type_for_field_content = mapper.map(effective_type_to_map)

        if mapped_type_for_field_content is None:
            raise TypeError(
                f"Could not map field '{field_name}' of Pydantic model '{model_name}' "
                f"with Pydantic type hint '{python_type_hint}' (effective type to map: '{effective_type_to_map}') to a GraphQL type."
            )

        if is_outer_optional:
            # Field is Optional[X]. GraphQL type for the field should be the mapping of X.
            # If mapping of X resulted in NonNull(Y), we use Y because Optional makes the field itself nullable.
            if isinstance(mapped_type_for_field_content, GraphQLNonNull):
                final_graphql_type = mapped_type_for_field_content.of_type
            else:
                final_graphql_type = mapped_type_for_field_content
        else:
            # Field is X (not Optional). GraphQL type for the field should be NonNull(mapping of X).
            # If mapping of X already resulted in NonNull(Y), that's fine. Otherwise, wrap mapping of X.
            if isinstance(mapped_type_for_field_content, GraphQLNonNull):
                final_graphql_type = mapped_type_for_field_content
            else:
                # We need to wrap with GraphQLNonNull if it's a type that can be wrapped
                # and is currently nullable.
                # graphql.is_output_type is a good check for valid output types.
                # graphql.is_nullable_type checks if it's not already NonNull and can be made NonNull.
                if graphql.is_output_type(mapped_type_for_field_content) and \
                   graphql.is_nullable_type(mapped_type_for_field_content):
                    final_graphql_type = GraphQLNonNull(mapped_type_for_field_content)
                else:
                    # If it's not a nullable output type (e.g., already NonNull via some other path,
                    # or a type like Union that can't be wrapped by NonNull), use it as is.
                    final_graphql_type = mapped_type_for_field_content

        # Resolve function for the field (remains the same)
        def resolve_field(obj: BaseModel, info, field_name_capture=field_name):
            return getattr(obj, field_name_capture, None)

        graphql_fields[to_camel_case(field_name)] = GraphQLField(
            final_graphql_type,
            resolve=resolve_field,
            description=field_info.description, # For Pydantic v2
        )

    return GraphQLObjectType(
        name=model_name,
        fields=graphql_fields,
        description=model_description,
    )
