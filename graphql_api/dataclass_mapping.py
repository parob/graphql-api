import typing_inspect
from typing import Type, get_type_hints

from docstring_parser import parse_from_object
from graphql.type.definition import (
    GraphQLType,
    GraphQLObjectType,
    GraphQLField,
    GraphQLInputField,
    GraphQLNonNull,
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
    base_type: GraphQLObjectType = mapper.map(cls, use_graphql_type=False)
    docstrings = parse_from_object(cls)

    # Unwrap the base_type if it is wrapped by GraphQLNonNull or a list type
    while hasattr(base_type, "of_type"):
        base_type = base_type.of_type

    # If we are generating input types, just return the base type
    if mapper.as_input:
        return base_type

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
        param_descriptions[doc_param.arg_name] = to_camel_case_text(
            doc_param.description
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
            # noinspection PyTypeChecker
            graph_type = GraphQLNonNull(graph_type)

        # Create the appropriate GraphQL field
        if mapper.as_input:
            # noinspection PyTypeChecker
            return GraphQLInputField(type_=graph_type, description=doc_description)
        else:
            # For output fields, a resolver that returns the property from the instance
            def resolver(instance, info=None, context=None, *args, **kwargs):
                return getattr(instance, property_name)

            # noinspection PyTypeChecker
            return GraphQLField(
                type_=graph_type, resolve=resolver, description=doc_description
            )

    # Define a factory function that returns a callable to generate all fields ---
    def fields_factory():
        """
        Returns a callable that creates the final dictionary of fields for this type.
        """
        existing_fields_fn = (
            base_type._fields
        )  # This might be a function on some GraphQL implementations

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
            if existing_fields_fn:
                try:
                    existing_fields = (
                        existing_fields_fn()
                    )  # might raise AssertionError in some libs
                    for existing_name, existing_field in existing_fields.items():
                        if existing_name not in new_fields:
                            new_fields[existing_name] = existing_field
                except AssertionError:
                    pass

            return new_fields

        return generate_fields

    # Override the _fields attribute on the base type with our custom factory ---
    base_type._fields = fields_factory()
    return base_type
