from typing import List

from uuid import UUID, uuid4

from graphql_api import type, field


@type(interface=True)
class Node:
    """
    The `Node` Interface type represents a Relay Node.
    `https://facebook.github.io/relay/graphql/objectidentification.htm`
    """

    # noinspection PyShadowingBuiltins
    def __init__(self, id: UUID = None, *args, **kwargs):
        if id is None:
            id = uuid4()

        self.id = id
        super().__init__(*args, **kwargs)

    @property
    @field
    def _id(self) -> UUID:
        return self.id


@type
class PageInfo:
    """
    The `PageInfo` Object type represents a Relay PageInfo.
    `https://facebook.github.io/relay/graphql/connections.htm#sec-undefined.PageInfo`
    """

    def __init__(
        self,
        has_previous_page: bool,
        has_next_page: bool,
        start_cursor: str,
        end_cursor: str,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._has_previous_page = has_previous_page
        self._has_next_page = has_next_page
        self._start_cursor = start_cursor
        self._end_cursor = end_cursor

    @property
    @field
    def has_previous_page(self) -> bool:
        return self._has_previous_page

    @property
    @field
    def has_next_page(self) -> bool:
        return self._has_next_page

    @property
    @field
    def start_cursor(self) -> str:
        return self._start_cursor

    @property
    @field
    def end_cursor(self) -> str:
        return self._end_cursor

    @property
    @field
    def count(self) -> int:
        return self._count


@type
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
    @field
    def node(self) -> Node:
        return self._node

    @property
    @field
    def cursor(self) -> str:
        return self._cursor


@type
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
        last: int = None,
        *args,
        **kwargs,
    ):
        self._before = before
        self._after = after
        self._first = first
        self._last = last
        super().__init__(*args, **kwargs)

    @field
    def edges(self) -> List[Edge]:
        raise NotImplementedError(
            f"{self.__class__.__name__} has not " f"implemented 'Connection.edges'"
        )

    @field
    def page_info(self) -> PageInfo:
        raise NotImplementedError(
            f"{self.__class__.__name__} has not " f"implemented 'Connection.page_info'"
        )
