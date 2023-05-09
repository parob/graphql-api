import enum
import sys

import pytest

from dataclasses import dataclass
from typing import Union, Optional, Literal, List

from graphql import GraphQLSchema
from requests.api import request
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

# noinspection PyPackageRequirements
from graphql.utilities import print_schema

from graphql_api.utils import executor_to_ast
from graphql_api.error import GraphQLError
from graphql_api.context import GraphQLContext
from graphql_api.api import GraphQLAPI


class TestDataclass:
    def test_dataclass(self):
        api = GraphQLAPI()

        # noinspection PyUnusedLocal
        @api.type(root=True)
        @dataclass
        class Root:
            hello_world: str = "hello world"
            hello_world_optional: Optional[str] = None

        executor = api.executor()

        test_query = """
            query HelloWorld {
                helloWorld
                helloWorldOptional
            }
        """

        result = executor.execute(test_query)

        expected = {"helloWorld": "hello world", "helloWorldOptional": None}
        assert not result.errors
        assert result.data == expected

    def test_dataclas_inheritance(self):
        api = GraphQLAPI()

        @dataclass
        class Person:
            name: str

        # noinspection PyUnusedLocal
        @api.type(root=True)
        @dataclass
        class Root:
            person: Person = Person(name="rob")

        executor = api.executor()

        test_query = """
            query {
                person { name }
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data == {"person": {"name": "rob"}}
