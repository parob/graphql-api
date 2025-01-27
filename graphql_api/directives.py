import json
from typing import Dict
from graphql import GraphQLDirective

from graphql_api.api import add_schema_directives
from graphql_api.utils import to_camel_case


class LocatedSchemaDirective:
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


class SchemaDirective(GraphQLDirective):
    def __call__(self, *args, **kwargs):
        if len(args) > 0:
            func = args[0]
            if callable(func):
                add_schema_directives(
                    func, [LocatedSchemaDirective(directive=self, args=kwargs)]
                )
                return func
        else:
            return lambda t: add_schema_directives(
                t, [LocatedSchemaDirective(directive=self, args=kwargs)]
            )
