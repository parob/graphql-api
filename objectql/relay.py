from typing import List

from uuid import UUID, uuid4

from objectql.schema import ObjectQLSchema

try:
    # noinspection PyUnresolvedReferences
    from dataclasses import dataclass, field

except ImportError:

    @ObjectQLSchema.interface
    class Node:
        """
        The `Node` Interface type represents a Relay Node.
        `https://facebook.github.io/relay/graphql/objectidentification.htm`
        """
        id: UUID

        def __init__(self, id: UUID = None, *args, **kwargs):
            if id is None:
                id = uuid4()

            self._id = id
            super().__init__(*args, **kwargs)

        @property
        @ObjectQLSchema.field.query
        def id(self) -> UUID:
            return self._id

    class PageInfo:
        """
        The `PageInfo` Object type represents a Relay PageInfo.
        `https://facebook.github.io/relay/graphql/connections.htm#sec-undefined.PageInfo`
        """

        def __init__(self,
                     has_previous_page: bool,
                     has_next_page: bool,
                     start_cursor: str,
                     end_cursor: str,
                     count: int, *args, **kwargs):

            super().__init__(*args, **kwargs)

            self._has_previous_page = has_previous_page
            self._has_next_page = has_next_page
            self._start_cursor = start_cursor
            self._end_cursor = end_cursor
            self._count = count

        @property
        @ObjectQLSchema.field.query
        def has_previous_page(self) -> bool:
            return self._has_previous_page

        @property
        @ObjectQLSchema.field.query
        def has_next_page(self) -> bool:
            return self._has_next_page

        @property
        @ObjectQLSchema.field.query
        def start_cursor(self) -> str:
            return self._start_cursor

        @property
        @ObjectQLSchema.field.query
        def end_cursor(self) -> str:
            return self._end_cursor

        @property
        @ObjectQLSchema.field.query
        def count(self) -> int:
            return self._count

    class Edge:
        """
        The `Edge` Object type represents a Relay Edge.
        `https://facebook.github.io/relay/graphql/connections.htm#sec-Edge-Types`
        """

        def __init__(self, node: Node, cursor: str, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self._node = node
            self._cursor = cursor

        @property
        @ObjectQLSchema.field.query
        def node(self) -> Node:
            return self._node

        @property
        @ObjectQLSchema.field.query
        def cursor(self) -> str:
            return self._cursor

else:

    @ObjectQLSchema.interface
    @dataclass
    class Node:
        """
        The `Node` Interface type represents a Relay Node.
        `https://facebook.github.io/relay/graphql/objectidentification.htm`
        """

        id: UUID = field(default_factory=uuid4)

    @dataclass
    class PageInfo:
        """
        The `PageInfo` Object type represents a Relay PageInfo.
        `https://facebook.github.io/relay/graphql/connections.htm#sec-undefined.PageInfo`
        """
        has_previous_page: bool
        has_next_page: bool
        start_cursor: str
        end_cursor: str

    @dataclass
    class Edge:
        """
        The `Edge` Object type represents a Relay Edge.
        `https://facebook.github.io/relay/graphql/connections.htm#sec-Edge-Types`
        """
        node: Node
        cursor: str


class Connection:
    """
    The `Connection` Object type represents a Relay Connection.
    `https://facebook.github.io/relay/graphql/connections.htm#sec-Connection-Types`
    """

    def __init__(
        self,
        before: str = None,
        after: str = None,
        first: int = None,
        last: int = None, *args, **kwargs
    ):
        self._before = before
        self._after = after
        self._first = first
        self._last = last
        super().__init__(*args, **kwargs)

    @ObjectQLSchema.field.query
    def edges(self) -> List[Edge]:
        raise NotImplementedError(
            f"{self.__class__.__name__} has not "
            f"implemented 'Connection.edges'"
        )

    @ObjectQLSchema.field.query
    def page_info(self) -> PageInfo:
        raise NotImplementedError(
            f"{self.__class__.__name__} has not "
            f"implemented 'Connection.page_info'"
        )
