import collections
from dataclasses import dataclass
from typing import List

from objectql.relay import Node, Connection, Edge, PageInfo

from objectql import query, ObjectQLSchemaBuilder


class TestRelay:

    def test_relay_query(self):
        api = ObjectQLSchemaBuilder()

        @dataclass
        class Person(Node):
            name: str = ""

        class PersonConnection(Connection):

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
                    self.filtered_cursors = self.filtered_cursors[:self._first]

                elif self._last is not None:
                    self.filtered_cursors = self.filtered_cursors[-self._last:]

            @query
            def edges(self) -> List[Edge]:
                return [Edge(cursor=cursor, node=self.people[cursor]) for cursor in self.filtered_cursors]

            @query
            def page_info(self) -> PageInfo:
                return PageInfo(
                    start_cursor=self.filtered_cursors[0],
                    end_cursor=self.filtered_cursors[-1],
                    has_previous_page=self.has_previous_page,
                    has_next_page=self.has_next_page
                )

        class Root:

            @query
            def people(self, before: str = None, after: str = None, first: int = None, last: int = None) -> Connection:
                _people = collections.OrderedDict([
                    ("a", Person(name="rob")), ("b", Person(name="dan")), ("c", Person(name="lily"))])
                return PersonConnection(_people, before=before, after=after, first=first, last=last)

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetPeopleNextPage {
                people {
                    pageInfo {
                        hasNextPage
                    }
                }
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "people": {
                "pageInfo": {
                    "hasNextPage": False
                }
            }
        }
        assert not result.errors
        assert result.data == expected

        test_query = '''
            query GetPeopleNames {
                people(first: 1, after: "a")  {
                    edges {
                        node {
                        ... on Person {
                                name
                            }
                        }
                    }
                }
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "people": {
                "edges": [{
                    "node": {
                        "name": "rob"
                    }
                }]
            }
        }
        assert not result.errors
        assert result.data == expected