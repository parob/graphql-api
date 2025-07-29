from typing import Type, get_type_hints

import typing_inspect
from docstring_parser import parse_from_object
from graphql.type.definition import (
    GraphQLField,
    GraphQLInputField,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLType,
    get_named_type,
    is_nullable_type,
    is_input_type,
    is_output_type,
)

from graphql_api.utils import to_camel_case, to_camel_case_text


def type_is_dataclass(cls: Type) -> bool:
    """
    Return True if the given class is a dataclass; otherwise False.
    """
    try:
        from dataclasses import is_dataclass
    except ImportError:
        return False
    return is_dataclass(cls)


# noinspection PyUnresolvedReferences
def type_from_dataclass(cls: Type, mapper) -> GraphQLType:
    """
    Map a Python dataclass to a GraphQL type using the given `mapper`.

    - Reads docstrings from the dataclass to set field descriptions.
    - Handles optional fields by wrapping them in GraphQLNonNull if not nullable.
    - Converts Python names to camelCase for the resulting GraphQL fields.
    - Merges any fields that already exist on the base (e.g., from inherited classes).
    """
    # Retrieve dataclass info, docstrings, and the base GraphQL type ---
    # noinspection PyUnresolvedReferences
    dataclass_fields = dict(cls.__dataclass_fields__)
    dataclass_types = get_type_hints(cls)
    initial_mapped_type: GraphQLType = mapper.map(cls, use_graphql_type=False)

    if mapper.as_input:
        # If mapping for input, initial_mapped_type should be an input type.
        # We can optionally assert this, then return it.
        _unwrapped_input_type = get_named_type(initial_mapped_type)
        if not is_input_type(_unwrapped_input_type):
            # This would indicate an issue with how mapper.map handles dataclasses in input mode.
            raise TypeError(
                f"Internal Error: Dataclass {cls.__name__} when mapped as input "
                f"should result in a GraphQLInputType, but got {type(_unwrapped_input_type)}."
            )
        return initial_mapped_type

    # If not mapper.as_input, proceed to map as a GraphQLObjectType (output type).
    docstrings = parse_from_object(cls)

    # Unwrap to the named type and ensure it's an GraphQLObjectType for output processing
    _unwrapped_object_type = get_named_type(initial_mapped_type)
    if not isinstance(_unwrapped_object_type, GraphQLObjectType):
        raise TypeError(
            f"The GraphQL type for dataclass {cls.__name__} (as an output type) must be an GraphQLObjectType, "
            f"but got {type(_unwrapped_object_type)} after unwrapping."
        )
    base_type: GraphQLObjectType = _unwrapped_object_type

    # Fields to exclude if the dataclass provides a `graphql_exclude_fields` method
    exclude_fields = []
    if hasattr(cls, "graphql_exclude_fields"):
        exclude_fields = cls.graphql_exclude_fields()

    # Create a dictionary of valid dataclass properties ---
    # Filter out private (leading underscore) or explicitly excluded fields
    valid_properties = {
        name: (field, dataclass_types.get(name))
        for name, field in dataclass_fields.items()
        if not name.startswith("_") and name not in exclude_fields
    }

    # Build a lookup for docstring param descriptions ---
    param_descriptions = {}
    for doc_param in docstrings.params:
        # key = param name, value = processed description text
        param_descriptions[doc_param.arg_name] = (
            to_camel_case_text(doc_param.description)
            if doc_param.description is not None
            else None
        )

    # Define a function to create a single GraphQL field ---
    def create_graphql_field(property_name: str, field_type, doc_description: str):
        """
        Create a GraphQLField or GraphQLInputField based on the mapper configuration
        and the given property type (field_type).
        """
        # Determine nullability by checking if field_type is a Union containing `None`.
        nullable = False
        if typing_inspect.is_union_type(field_type):
            union_args = typing_inspect.get_args(field_type, evaluate=True)
            if type(None) in union_args:
                nullable = True

        # Map the Python type to a GraphQL type
        graph_type: GraphQLType = mapper.map(type_=field_type)

        # Wrap in GraphQLNonNull if it is not nullable
        if not nullable:
            # Only wrap if graph_type is a type that can be made non-null
            # and isn't already non-null.
            if is_nullable_type(graph_type):  # Check if it's a wrappable type
                graph_type = GraphQLNonNull(graph_type)  # type: ignore[arg-type]
            # If is_non_null_type(graph_type) is true, it's already non-null, so no change needed.
            # If neither, it's not a type that can be wrapped by GraphQLNonNull (e.g. GraphQLSchema), so no change.

        # Create the appropriate GraphQL field
        if mapper.as_input:
            if not is_input_type(graph_type):
                raise TypeError(
                    f"Type '{graph_type}' mapped for property '{property_name}' of dataclass '{cls.__name__}' "
                    f"is not a valid GraphQLInputType."
                )
            # The is_input_type check should refine graph_type.
            # If the type checker still complains, a specific ignore is needed.
            return GraphQLInputField(type_=graph_type, description=doc_description)  # type: ignore[arg-type]
        else:
            if not is_output_type(graph_type):
                raise TypeError(
                    f"Type '{graph_type}' mapped for property '{property_name}' of dataclass '{cls.__name__}' "
                    f"is not a valid GraphQLOutputType."
                )

            # For output fields, a resolver that returns the property from the instance
            def resolver(instance, info=None, context=None, *args, **kwargs):
                return getattr(instance, property_name)

            # The is_output_type check should refine graph_type.
            # If the type checker still complains, a specific ignore is needed.
            return GraphQLField(
                type_=graph_type, resolve=resolver, description=doc_description  # type: ignore[arg-type]
            )

    # Define a factory function that returns a callable to generate all fields ---
    def fields_factory():
        """
        Returns a callable that creates the final dictionary of fields for this type.
        """
        existing_fields_source = (
            base_type._fields
        )  # This might be a function or a direct mapping

        def generate_fields():
            """
            Build the final dictionary of fields by merging new fields derived from
            the dataclass properties with any existing fields on the base type.
            """
            new_fields = {}

            # Create a GraphQLField or GraphQLInputField for each valid property
            for name, (field, field_type) in valid_properties.items():
                # Use the docstring description if available
                doc_description = param_descriptions.get(name, None)

                # Generate the actual GraphQL field
                # noinspection PyTypeChecker
                graph_field = create_graphql_field(name, field_type, doc_description)

                # Use camelCase for the GraphQL field name
                camel_case_name = to_camel_case(name)
                new_fields[camel_case_name] = graph_field

            # Merge any existing fields on the base type (e.g., from inherited classes)
            if existing_fields_source:
                try:
                    if callable(existing_fields_source):
                        existing_fields = (
                            existing_fields_source()
                        )  # Call if it's a thunk
                    else:
                        existing_fields = (
                            existing_fields_source  # Use directly if it's a mapping
                        )

                    for existing_name, existing_field in existing_fields.items():
                        if existing_name not in new_fields:
                            new_fields[existing_name] = existing_field
                except AssertionError:  # pragma: no cover
                    # This might still be needed if calling the thunk itself raises an AssertionError
                    # in some edge cases or library versions.
                    pass

            return new_fields

        return generate_fields

    # Override the _fields attribute on the base type with our custom factory ---
    base_type._fields = fields_factory()
    return base_type
