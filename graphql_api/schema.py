import json
from typing import Dict, List, Optional, Union, cast

from graphql import (
    GraphQLDirective,
    GraphQLField,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLType,
    is_interface_type,
    is_object_type,
    GraphQLInterfaceType,
)

from graphql_api.directives import SchemaDirective
from graphql_api.utils import to_camel_case


class EnumValue:
    """
    A utility class for creating enum values that can hold directive information.
    This allows enum values to be decorated with directives for GraphQL schema generation.
    """
    def __init__(self, value: str, directive=None):
        self.value = value
        self.directive = directive
        # Store the directive as an applied directive so it can be detected
        if directive:
            self._applied_directives = [AppliedDirective(directive=directive, args={})]

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"EnumValue('{self.value}')"

    def __eq__(self, other):
        if isinstance(other, EnumValue):
            return self.value == other.value
        return self.value == other

    def __hash__(self):
        return hash(self.value)


class AppliedDirective:
    def __init__(self, directive: Union[GraphQLDirective, SchemaDirective], args: Dict):
        self.directive = (
            directive.directive if isinstance(directive, SchemaDirective) else directive
        )
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


def add_applied_directives(value, directives: List[AppliedDirective]):
    if directives:
        if hasattr(value, "_applied_directives"):
            directives = [*directives, *getattr(value, "_applied_directives", [])]

        value._applied_directives = directives
    return value


def get_applied_directives(value) -> List[AppliedDirective]:
    if hasattr(value, "_applied_directives"):
        return getattr(value, "_applied_directives")
    return []


def get_directives(
    graphql_type: Union[GraphQLType, GraphQLField],
    _fetched_types: Optional[List[Union[GraphQLNamedType, GraphQLField]]] = None,
) -> Dict[str, GraphQLDirective]:
    _directives = {}
    if not _fetched_types:
        _fetched_types = []
    while isinstance(graphql_type, (GraphQLNonNull, GraphQLList)):
        graphql_type = graphql_type.of_type
    if not isinstance(graphql_type, (GraphQLNamedType, GraphQLField)):
        return _directives
    if graphql_type not in _fetched_types:
        _fetched_types.append(graphql_type)
        for schema_directive in get_applied_directives(graphql_type):
            directive = schema_directive.directive
            _directives[directive.name] = directive

        if is_object_type(graphql_type) or is_interface_type(graphql_type):
            graphql_type = cast(
                Union[GraphQLObjectType, GraphQLInterfaceType], graphql_type
            )
            for _field in graphql_type.fields.values():
                _field: GraphQLField
                _directives.update(get_directives(_field, _fetched_types))
                _directives.update(get_directives(_field.type, _fetched_types))

    return _directives
