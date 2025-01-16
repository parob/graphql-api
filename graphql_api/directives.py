from typing import Dict
from graphql import GraphQLDirective


class SchemaDirective:

    def __init__(self, directive: GraphQLDirective, args: Dict):
        self.directive = directive
        self.args = args
