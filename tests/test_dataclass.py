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

    def test_unused_mutable_types_filtered_out_simple(self):
        """
        Test that unused mutable types are correctly filtered out.

        This simpler test shows that when only some types are used by mutable fields,
        unused mutable type variants should be filtered out.
        """

        class UsedType:
            """This type will be used by a mutable field"""
            def __init__(self):
                self._value = "used"

            @field
            def value(self) -> str:
                return self._value

        class UnusedType:
            """This type will NOT be used by any mutable field"""
            def __init__(self):
                self._data = "unused"

            @field
            def data(self) -> str:
                return self._data

        class AnotherUnusedType:
            """Another unused type"""
            def __init__(self):
                self._info = "also unused"

            @field
            def info(self) -> str:
                return self._info

        class Root:
            @field
            def used_object(self) -> UsedType:
                """Query field that returns UsedType"""
                return UsedType()

            @field
            def unused_object(self) -> UnusedType:
                """Query field that returns UnusedType"""
                return UnusedType()

            @field
            def another_unused_object(self) -> AnotherUnusedType:
                """Query field that returns AnotherUnusedType"""
                return AnotherUnusedType()

            # Only ONE mutable field that only uses UsedType
            @field(mutable=True)
            def update_used(self, value: str) -> UsedType:
                """Only mutable operation - only UsedType should get a mutable version"""
                obj = UsedType()
                obj._value = value
                return obj

        # Build the API using the decorator approach like the working test
        api = GraphQLAPI()

        # Register all types with the API
        api.type(UsedType)
        api.type(UnusedType)
        api.type(AnotherUnusedType)
        api.type(Root, is_root_type=True)

        schema, _ = api.build_schema()

        type_map = schema.type_map
        print(f"All types in schema: {sorted([k for k in type_map.keys() if not k.startswith('__')])}")

        # Check that query types exist (should all be present)
        expected_query_types = {"Root", "UsedType", "UnusedType", "AnotherUnusedType"}
        for type_name in expected_query_types:
            assert type_name in type_map, f"{type_name} should be present in query schema"

        # Check that only UsedType gets a mutable version (since only update_used is mutable)
        assert "UsedTypeMutable" in type_map, "UsedTypeMutable should exist since update_used returns UsedType"

        # Critical test: Other types should NOT have mutable versions
        unused_mutable_types = {"UnusedTypeMutable", "AnotherUnusedTypeMutable"}

        for mutable_type in unused_mutable_types:
            assert mutable_type not in type_map, f"{mutable_type} should be filtered out as it's unused"

        # Verify mutation works
        executor = api.executor()

        result = executor.execute("""
            mutation TestUpdate {
                updateUsed(value: "new value") {
                    value
                }
            }
        """)

        assert not result.errors, f"Mutation should succeed but got errors: {result.errors}"
        assert result.data == {
            "updateUsed": {
                "value": "new value"
            }
        }

    def test_unused_mutable_types_bug_demonstration(self):
        """
        This test demonstrates the BUG where mutable versions are created for ALL types
        used anywhere in the schema, not just types returned by mutable fields.

        EXPECTED BEHAVIOR: Only UserMutable should exist since only update_user is mutable
        ACTUAL BEHAVIOR: BookMutable also exists because Book is used in a query field

        This is the same issue reported in the library app example.
        """
        from enum import Enum

        class UserRole(Enum):
            READER = "READER"
            AUTHOR = "AUTHOR"

        class User:
            def __init__(self, id: str, name: str, email: str, role: UserRole):
                self._id = id
                self._name = name
                self._email = email
                self._role = role

            @field
            def id(self) -> str:
                return self._id

            @field
            def name(self) -> str:
                return self._name

            @field
            def email(self) -> str:
                return self._email

            @field
            def role(self) -> UserRole:
                return self._role

        class Book:
            def __init__(self, id: str, title: str, author: str):
                self._id = id
                self._title = title
                self._author = author

            @field
            def id(self) -> str:
                return self._id

            @field
            def title(self) -> str:
                return self._title

            @field
            def author(self) -> str:
                return self._author

        class Root:
            @field
            def user(self, id: str) -> Optional[User]:
                """Query field that returns User"""
                return User("1", "John Doe", "john@example.com", UserRole.READER)

            @field
            def book(self, id: str) -> Optional[Book]:
                """Query field that returns Book - this SHOULD NOT create BookMutable"""
                return Book("1", "Great Gatsby", "F. Scott Fitzgerald")

            @field(mutable=True)
            def update_user(self, id: str, name: str, email: str) -> Optional[User]:
                """Mutable field - this SHOULD create UserMutable"""
                return User(id, name, email, UserRole.READER)

            # NOTE: No mutable fields return Book, so BookMutable should NOT exist

        api = GraphQLAPI(root_type=Root)
        schema, _ = api.build_schema()
        type_map = schema.type_map

        print("\\nDemonstrating the bug:")
        print(f"Types in schema: {sorted([k for k in type_map.keys() if not k.startswith('__')])}")

        # This assertion SHOULD pass (UserMutable is needed)
        assert "UserMutable" in type_map, "UserMutable should exist since update_user returns User"

        # This assertion should now PASS - BookMutable should be filtered out
        if "BookMutable" in type_map:
            print("❌ BUG STILL EXISTS: BookMutable exists even though no mutable field returns Book")
            print("   This is the same issue from the library app where all types get mutable versions")
        else:
            print("✅ Bug fixed: BookMutable correctly filtered out")

        # Now that the bug is fixed, this assertion should pass:
        assert "BookMutable" not in type_map, "BookMutable should be filtered out since no mutable field returns Book"

        # Test that queries and mutations still work
        executor = api.executor()

        # Query should work
        query_result = executor.execute("""
            query TestQuery {
                book(id: "1") {
                    title
                    author
                }
            }
        """)
        assert not query_result.errors
        assert query_result.data == {"book": {"title": "Great Gatsby", "author": "F. Scott Fitzgerald"}}

        # Mutation should work
        mutation_result = executor.execute("""
            mutation TestMutation {
                updateUser(id: "123", name: "Jane Doe", email: "jane@example.com") {
                    name
                }
            }
        """)
        assert not mutation_result.errors
        assert mutation_result.data == {"updateUser": {"name": "Jane Doe"}}
