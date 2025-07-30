from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field
from graphql_api.reduce import GraphQLFilter, FilterResponse


class TestDataclass:
    def test_dataclass(self):
        api = GraphQLAPI()

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
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

    def test_dataclass_inheritance(self):
        api = GraphQLAPI()

        @dataclass
        class Entity:
            name: str
            embedding: List[float]

        @dataclass
        class Person(Entity):
            name: str
            embedding: List[float]

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        @dataclass
        class Root:
            person: Person

        executor = api.executor(
            root_value=Root(person=Person(name="rob", embedding=[1, 2]))
        )

        test_query = """
            query {
                person { name, embedding }
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data == {"person": {"name": "rob", "embedding": [1, 2]}}

    def test_allow_transitive_preserves_all_fields_on_dataclass(self):
        """
        Test that ALLOW_TRANSITIVE correctly preserves all available fields
        on a dataclass-based GraphQL type when the type is kept by filtering.

        This tests the scenario where a field like getStats returns a Stats type with multiple fields
        (conversationsCount, messagesCount, usersCount) and all fields should be available after filtering.
        """

        class Timeframe(Enum):
            LAST_30_DAYS = "LAST_30_DAYS"
            LAST_7_DAYS = "LAST_7_DAYS"

        @dataclass
        class Stats:
            """Stats dataclass with multiple fields that should all be preserved"""

            @field({"tags": ["admin"]})  # This field should be filtered out normally
            def conversations_count(self) -> int:
                return 42

            @field({"tags": ["admin"]})  # This field should be filtered out normally
            def messages_count(self) -> int:
                return 100

            @field({"tags": ["admin"]})  # Third field to make the bug more obvious
            def users_count(self) -> int:
                return 15

        @dataclass
        class Root:
            @field({"tags": ["admin"]})  # This field should use ALLOW_TRANSITIVE
            def get_stats(self, timeframe: Timeframe) -> Stats:
                """Field that returns Stats - should preserve Stats type with ALLOW_TRANSITIVE"""
                return Stats()

        # Create a custom filter that uses ALLOW_TRANSITIVE for get_stats field
        class TestFilter(GraphQLFilter):
            def filter_field(self, name: str, meta: dict) -> FilterResponse:
                tags = meta.get("tags", [])
                if "admin" in tags:
                    if name == "get_stats":
                        # Use ALLOW_TRANSITIVE to preserve the Stats type
                        return FilterResponse.ALLOW_TRANSITIVE
                    else:
                        # Other admin fields should be removed
                        return FilterResponse.REMOVE_STRICT
                return FilterResponse.ALLOW

        # Build the API with the custom filter
        api = GraphQLAPI(root_type=Root, filters=[TestFilter()])
        schema, _ = api.build_schema()

        type_map = schema.type_map

        print(f"Types in schema: {sorted([k for k in type_map.keys() if not k.startswith('__')])}")

        # Stats should be preserved due to ALLOW_TRANSITIVE
        assert "Stats" in type_map, "Stats type should be preserved due to ALLOW_TRANSITIVE"

        # Check that Stats type exists and has fields
        from graphql import GraphQLObjectType
        stats_type = type_map["Stats"]
        assert isinstance(stats_type, GraphQLObjectType)

        stats_fields = list(stats_type.fields.keys())
        print(f"Stats fields: {stats_fields}")

        # ALLOW_TRANSITIVE should preserve ALL fields on the type, not just one
        assert len(stats_fields) == 3, f"Expected 3 fields (conversationsCount, messagesCount, usersCount) but got {len(stats_fields)}: {stats_fields}"

        expected_fields = {"conversationsCount", "messagesCount", "usersCount"}
        actual_fields = set(stats_fields)
        assert expected_fields == actual_fields, f"Expected {expected_fields} but got {actual_fields}"

        # Test that a query actually works and returns all fields
        executor = api.executor(root_value=Root())

        test_query = """
            query MyQuery {
                getStats(timeframe: LAST_30_DAYS) {
                    conversationsCount
                    messagesCount
                    usersCount
                }
            }
        """

        result = executor.execute(test_query)

        print(f"Query result: {result}")
        print(f"Query errors: {result.errors}")

        # This should work with ALLOW_TRANSITIVE preserving all fields
        assert not result.errors, f"Query should succeed but got errors: {result.errors}"
        assert result.data == {
            "getStats": {
                "conversationsCount": 42,
                "messagesCount": 100,
                "usersCount": 15
            }
        }, f"Expected all three fields but got: {result.data}"
