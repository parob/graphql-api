import json
from typing import Dict, List

from graphql import (
    GraphQLDirective,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLList,
    is_object_type,
    is_interface_type,
    GraphQLField,
    GraphQLType,
)

from graphql_api.utils import to_camel_case


class AppliedSchemaDirective:
    def __init__(self, directive: GraphQLDirective, args: Dict):
        self.directive = directive
        self.args = args

    def print(self) -> str:
        directive_name = str(self.directive)
        if len(self.directive.args) == 0:
            return directive_name

        # Format each keyword argument as a string, considering its type
        formatted_args = [
            (
                f"{to_camel_case(key)}: "
                + (f'"{value}"' if isinstance(value, str) else json.dumps(value))
            )
            for key, value in self.args.items()
            if value is not None and to_camel_case(key) in self.directive.args
        ]
        if not formatted_args:
            return directive_name

        # Construct the directive string
        return f"{directive_name}({', '.join(formatted_args)})"


def add_schema_directives(value, directives):
    if directives:
        if hasattr(value, "_schema_directives"):
            directives = [*directives, *getattr(value, "_schema_directives", [])]

        value._schema_directives = directives
    return value


def get_schema_directives(value) -> List[AppliedSchemaDirective]:
    if hasattr(value, "_schema_directives"):
        return getattr(value, "_schema_directives")
    return []


def get_directives(
    graphql_type: GraphQLType, _fetched_types: List[GraphQLNamedType] = None
) -> Dict[str, GraphQLDirective]:
    _directives = {}
    if not _fetched_types:
        _fetched_types = []
    while isinstance(graphql_type, (GraphQLNonNull, GraphQLList)):
        graphql_type = graphql_type.of_type
    if graphql_type not in _fetched_types:
        _fetched_types.append(graphql_type)
        for schema_directive in get_schema_directives(graphql_type):
            directive = schema_directive.directive
            _directives[directive.name] = directive

        if is_object_type(graphql_type) or is_interface_type(graphql_type):
            for _field in graphql_type.fields.values():
                _field: GraphQLField
                _directives.update(get_directives(_field.type, _fetched_types))

    return _directives
