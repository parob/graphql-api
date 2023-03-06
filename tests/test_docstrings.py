import enum
import sys

import pytest

from dataclasses import dataclass
from typing import Union, Optional

from graphql import GraphQLSchema
from requests.api import request
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

# noinspection PyPackageRequirements
from graphql.utilities import print_schema

from graphql_api.utils import executor_to_ast
from graphql_api.error import GraphQLError
from graphql_api.context import GraphQLContext
from graphql_api.api import GraphQLAPI, GraphQLRootTypeDelegate
from graphql_api.reduce import TagFilter
from graphql_api.remote import GraphQLRemoteExecutor, remote_execute
from graphql_api.decorators import field


class TestGraphQL:

    def test_basic_docstring(self):
        api = GraphQLAPI()

        class Node:
            """
            NODE_DOCSTRING
            """

            @api.field
            def node_field(self, test: int) -> int:
                """
                NODE_FIELD_DOCSTRING
                """
                return test * test

        @api.type(root=True)
        class Root:
            """
            ROOT_DOCSTRING
            """

            @api.field
            def root_field(self) -> Node:
                """
                ROOT_FIELD_DOCSTRING
                """
                return Node()

        schema = api.graphql_schema()[0]

        assert schema.query_type.description == "ROOT_DOCSTRING"

        root_field = schema.query_type.fields['rootField']

        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        root_field_type = root_field.type.of_type

        assert root_field_type.description == "NODE_DOCSTRING"

        node_field = root_field_type.fields["nodeField"]

        assert node_field.description == "NODE_FIELD_DOCSTRING"

    def test_basic_dataclass_docstring(self):
        api = GraphQLAPI()

        @dataclass
        class Node:
            """
            NODE_DOCSTRING
            """
            string_field: Optional[str] = None
            int_field: Optional[int] = None

            @api.field
            def node_field(self, test: int) -> int:
                """
                NODE_FIELD_DOCSTRING
                """
                return test * test

        @api.type(root=True)
        class Root:
            """
            ROOT_DOCSTRING
            """

            @api.field
            def root_field(self) -> Node:
                """
                ROOT_FIELD_DOCSTRING
                """
                return Node()

        schema = api.graphql_schema()[0]

        assert schema.query_type.description == "ROOT_DOCSTRING"

        root_field = schema.query_type.fields['rootField']

        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        root_field_type = root_field.type.of_type

        assert root_field_type.description == "NODE_DOCSTRING"

        node_field = root_field_type.fields["nodeField"]

        assert node_field.description == "NODE_FIELD_DOCSTRING"

    def test_parsed_dataclass_docstring(self):
        api = GraphQLAPI()

        @dataclass
        class Node:
            """
            NODE_DOCSTRING
            """
            string_field: Optional[str] = None
            """STRING_FIELD_DOCSTRING"""
            int_field: Optional[int] = None
            """INT_FIELD_DOCSTRING"""

            @api.field
            def node_field(self, test: int) -> int:
                """
                NODE_FIELD_DOCSTRING
                """
                return test * test

        @api.type(root=True)
        class Root:
            """
            ROOT_DOCSTRING
            """

            @api.field
            def root_field(self) -> Node:
                """
                ROOT_FIELD_DOCSTRING
                """
                return Node()

        schema = api.graphql_schema()[0]

        assert schema.query_type.description == "ROOT_DOCSTRING"

        root_field = schema.query_type.fields['rootField']

        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        root_field_type = root_field.type.of_type

        assert root_field_type.description == "NODE_DOCSTRING"

        string_field = root_field_type.fields["stringField"]
        int_field = root_field_type.fields["intField"]
        node_field = root_field_type.fields["nodeField"]

        assert string_field.description == "STRING_FIELD_DOCSTRING"
        assert int_field.description == "INT_FIELD_DOCSTRING"
        assert node_field.description == "NODE_FIELD_DOCSTRING"

    def test_google_dataclass_docstring(self):
        api = GraphQLAPI()

        @dataclass
        class Node:
            """
            NODE_DOCSTRING

            Args:
                string_field: STRING_FIELD_DOCSTRING
                int_field: INT_FIELD_DOCSTRING
            """
            string_field: Optional[str] = None
            int_field: Optional[int] = None

            @api.field
            def node_field(self, test: int) -> int:
                """
                NODE_FIELD_DOCSTRING
                """
                return test * test

        @api.type(root=True)
        class Root:

            @api.field
            def root_field(self) -> Node:
                return Node()

        schema = api.graphql_schema()[0]
        root_field = schema.query_type.fields['rootField']
        root_field_type = root_field.type.of_type

        string_field = root_field_type.fields["stringField"]
        int_field = root_field_type.fields["intField"]
        node_field = root_field_type.fields["nodeField"]

        assert string_field.description == "STRING_FIELD_DOCSTRING"
        assert int_field.description == "INT_FIELD_DOCSTRING"
        assert node_field.description == "NODE_FIELD_DOCSTRING"
