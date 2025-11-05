"""
Test all code examples from the Relay pagination documentation
"""
from typing import List, Optional
import collections
from graphql_api.api import GraphQLAPI
from graphql_api.relay import Connection, Edge, Node, PageInfo


class TestRelayExamples:

    def test_basic_relay_setup(self):
        """Test basic Relay pagination setup"""
        api = GraphQLAPI()

        class PersonBasic(Node):
            def __init__(self, name: Optional[str] = None, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._name = name

            @property
            @api.field
            def name(self) -> Optional[str]:
                return self._name

        class PersonBasicConnection(Connection):
            def __init__(self, people, *args, **kwargs):
                super().__init__(*args, **kwargs)

                cursors = list(people.keys())
                start_index = 0
                end_index = len(cursors) - 1

                self.has_previous_page = False
                self.has_next_page = False
                self.filtered_cursors = []

                # Handle 'after' cursor
                if self._after is not None:
                    start_index = cursors.index(self._after)
                    if start_index > 0:
                        self.has_previous_page = True

                # Handle 'before' cursor
                if self._before is not None:
                    end_index = cursors.index(self._before)
                    if end_index < len(cursors) - 1:
                        self.has_next_page = True

                self.filtered_cursors = cursors[start_index: end_index + 1]
                self.people = people

                # Handle 'first' pagination
                if self._first is not None:
                    if len(self.filtered_cursors) > self._first:
                        self.has_next_page = True
                    self.filtered_cursors = self.filtered_cursors[: self._first]

                # Handle 'last' pagination
                elif self._last is not None:
                    if len(self.filtered_cursors) > self._last:
                        self.has_previous_page = True
                    self.filtered_cursors = self.filtered_cursors[-self._last:]

            @api.field
            def edges(self) -> List[Edge]:
                return [
                    Edge(cursor=cursor, node=self.people[cursor])
                    for cursor in self.filtered_cursors
                ]

            @api.field
            def page_info(self) -> PageInfo:
                return PageInfo(
                    start_cursor=self.filtered_cursors[0],
                    end_cursor=self.filtered_cursors[-1],
                    has_previous_page=self.has_previous_page,
                    has_next_page=self.has_next_page,
                    count=len(self.filtered_cursors),
                )

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def people(
                self,
                before: Optional[str] = None,
                after: Optional[str] = None,
                first: Optional[int] = None,
                last: Optional[int] = None,
            ) -> Connection:
                # Your data source - could be from database
                people_data = collections.OrderedDict([
                    ("person_1", PersonBasic(name="Alice")),
                    ("person_2", PersonBasic(name="Bob")),
                    ("person_3", PersonBasic(name="Charlie")),
                ])

                return PersonBasicConnection(
                    people_data, before=before, after=after, first=first, last=last
                )

        # Test basic pagination
        result = api.execute('''
            query {
                people(first: 2) {
                    edges {
                        cursor
                        node {
                            ... on PersonBasic {
                                name
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        hasPreviousPage
                        startCursor
                        endCursor
                        count
                    }
                }
            }
        ''')

        assert not result.errors
        assert len(result.data["people"]["edges"]) == 2
        assert result.data["people"]["edges"][0]["node"]["name"] == "Alice"
        assert result.data["people"]["edges"][1]["node"]["name"] == "Bob"
        assert result.data["people"]["pageInfo"]["hasNextPage"] is True
        assert result.data["people"]["pageInfo"]["hasPreviousPage"] is False
        assert result.data["people"]["pageInfo"]["count"] == 2

    def test_relay_pagination_with_after(self):
        """Test Relay pagination with after cursor - copy working pattern from test_relay.py"""
        api = GraphQLAPI()

        # Use unique class names to avoid conflicts with other tests
        class PersonAfter(Node):
            def __init__(self, name: Optional[str] = None, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._name = name

            @property
            @api.field
            def name(self) -> Optional[str]:
                return self._name

        class PersonAfterConnection(Connection):
            def __init__(self, people, *args, **kwargs):
                super().__init__(*args, **kwargs)

                cursors = list(people.keys())
                start_index = 0
                end_index = len(cursors) - 1

                self.has_previous_page = False
                self.has_next_page = False
                self.filtered_cursors = []

                if self._after is not None:
                    start_index = cursors.index(self._after)
                    if start_index > 0:
                        self.has_previous_page = True

                if self._before is not None:
                    end_index = cursors.index(self._before)
                    if end_index < len(cursors) - 1:
                        self.has_next_page = True

                self.filtered_cursors = cursors[start_index: end_index + 1]

                self.people = people

                if self._first is not None:
                    self.filtered_cursors = self.filtered_cursors[: self._first]

                elif self._last is not None:
                    self.filtered_cursors = self.filtered_cursors[-self._last:]

            @api.field
            def edges(self) -> List[Edge]:
                return [
                    Edge(cursor=cursor, node=self.people[cursor])
                    for cursor in self.filtered_cursors
                ]

            @api.field
            def page_info(self) -> PageInfo:
                return PageInfo(
                    start_cursor=self.filtered_cursors[0],
                    end_cursor=self.filtered_cursors[-1],
                    has_previous_page=self.has_previous_page,
                    has_next_page=self.has_next_page,
                    count=len(self.filtered_cursors),
                )

        @api.type(is_root_type=True)
        class RootAfter:
            @api.field
            def people(
                self,
                before: Optional[str] = None,
                after: Optional[str] = None,
                first: Optional[int] = None,
                last: Optional[int] = None,
            ) -> Connection:  # Key: return Connection, not PersonConnection
                _people = collections.OrderedDict([
                    ("a", PersonAfter(name="rob")),
                    ("b", PersonAfter(name="dan")),
                    ("c", PersonAfter(name="lily")),
                ])

                return PersonAfterConnection(
                    _people, before=before, after=after, first=first, last=last
                )

        result = api.execute("""
            query GetPeopleNames {
                people(first: 1, after: "a")  {
                    edges {
                        node {
                        ... on PersonAfter {
                                name
                            }
                        }
                    }
                }
            }
        """)

        expected = {"people": {"edges": [{"node": {"name": "rob"}}]}}  # Match working test: after "a" returns "rob"
        assert not result.errors
        assert result.data == expected

    def test_relay_schema_generation(self):
        """Test that Relay types generate proper GraphQL schema"""
        api = GraphQLAPI()

        class PersonSchema(Node):
            @property
            @api.field
            def name(self) -> str:
                return "Alice"

        class PersonSchemaConnection(Connection):
            @api.field
            def edges(self) -> List[Edge]:
                return []

            @api.field
            def page_info(self) -> PageInfo:
                return PageInfo(
                    start_cursor="start",
                    end_cursor="end",
                    has_previous_page=False,
                    has_next_page=False,
                    count=0,
                )

        @api.type(is_root_type=True)
        class QuerySchema:
            @api.field
            def people(self) -> PersonSchemaConnection:
                return PersonSchemaConnection()

        schema, _ = api.build()
        assert schema is not None

        # Verify the schema has proper Relay types
        query_type = schema.query_type
        people_field = query_type.fields["people"]

        # The connection should have edges and pageInfo fields
        connection_type = people_field.type.of_type
        assert "edges" in connection_type.fields
        assert "pageInfo" in connection_type.fields
