---
title: "Pagination and Relay"
weight: 3
description: >
  Implementing cursor-based pagination and Relay-compliant APIs
---

# Pagination and Relay

`graphql-api` provides comprehensive support for Relay-style cursor-based pagination, which is the GraphQL standard for efficiently handling large datasets. This includes the Node interface for global object identification and Connection-based pagination.

## Understanding Relay Pagination

Relay pagination uses a cursor-based approach that provides:
- **Stable pagination**: Results remain consistent even when data changes
- **Efficient traversal**: Forward and backward navigation through large datasets
- **Rich metadata**: Information about pagination state and boundaries
- **GraphQL standard**: Compatible with Relay, Apollo, and other GraphQL clients

## Core Relay Concepts

### Node Interface

The Node interface provides globally unique IDs for objects:

```python
from graphql_api.relay import Node

@api.type
class User(Node):
    def __init__(self, id: str, name: str, email: str):
        self._id = id
        self._name = name
        self._email = email

    # The `id` field is automatically provided by the Node interface
    @api.field
    def name(self) -> str:
        return self._name

    @api.field
    def email(self) -> str:
        return self._email

    @classmethod
    def get_node(cls, info, id):
        """
        This method tells Relay how to fetch a User by its global ID.
        In a real app, you would fetch the user from a database.
        """
        # Example implementation
        user_data = get_user_from_database(id)
        if user_data:
            return User(id=user_data.id, name=user_data.name, email=user_data.email)
        return None

@api.type
class Post(Node):
    def __init__(self, id: str, title: str, content: str, author_id: str):
        self._id = id
        self._title = title
        self._content = content
        self._author_id = author_id

    @api.field
    def title(self) -> str:
        return self._title

    @api.field
    def content(self) -> str:
        return self._content

    @api.field
    def author(self) -> User:
        return User.get_node(None, self._author_id)

    @classmethod
    def get_node(cls, info, id):
        post_data = get_post_from_database(id)
        if post_data:
            return Post(
                id=post_data.id,
                title=post_data.title,
                content=post_data.content,
                author_id=post_data.author_id
            )
        return None
```

### Connection, Edge, and PageInfo

Relay pagination uses these key components:

```python
from graphql_api.relay import Connection, Edge, PageInfo
from typing import List, Optional
import collections

class PersonConnection(Connection):
    def __init__(self, people, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Convert data to cursor-based format
        cursors = list(people.keys())
        start_index = 0
        end_index = len(cursors) - 1

        self.has_previous_page = False
        self.has_next_page = False
        self.filtered_cursors = []

        # Handle 'after' cursor - start after this cursor
        if self._after is not None:
            try:
                start_index = cursors.index(self._after) + 1
                if start_index > 0:
                    self.has_previous_page = True
            except ValueError:
                # Invalid cursor - start from beginning
                start_index = 0

        # Handle 'before' cursor - end before this cursor
        if self._before is not None:
            try:
                end_index = cursors.index(self._before) - 1
                if end_index < len(cursors) - 1:
                    self.has_next_page = True
            except ValueError:
                # Invalid cursor - go to end
                end_index = len(cursors) - 1

        # Apply cursor filtering
        self.filtered_cursors = cursors[start_index:end_index + 1]
        self.people = people

        # Handle 'first' pagination - limit from start
        if self._first is not None:
            if len(self.filtered_cursors) > self._first:
                self.filtered_cursors = self.filtered_cursors[:self._first]
                self.has_next_page = True

        # Handle 'last' pagination - limit from end
        elif self._last is not None:
            if len(self.filtered_cursors) > self._last:
                self.filtered_cursors = self.filtered_cursors[-self._last:]
                self.has_previous_page = True

    @api.field
    def edges(self) -> List[Edge]:
        """Return edges containing cursor and node for each item."""
        return [
            Edge(cursor=cursor, node=self.people[cursor])
            for cursor in self.filtered_cursors
        ]

    @api.field
    def page_info(self) -> PageInfo:
        """Return pagination metadata."""
        if not self.filtered_cursors:
            return PageInfo(
                start_cursor=None,
                end_cursor=None,
                has_previous_page=False,
                has_next_page=False,
                count=0
            )

        return PageInfo(
            start_cursor=self.filtered_cursors[0],
            end_cursor=self.filtered_cursors[-1],
            has_previous_page=self.has_previous_page,
            has_next_page=self.has_next_page,
            count=len(self.filtered_cursors),
        )
```

## Basic Pagination Implementation

Here's a complete example of Relay pagination:

```python
from graphql_api.relay import Node, Connection, Edge, PageInfo
from typing import List, Optional
import collections

class Person(Node):
    def __init__(self, name: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name = name

    @property
    @api.field
    def name(self) -> Optional[str]:
        return self._name

    @classmethod
    def get_node(cls, info, id):
        # In real implementation, fetch from database
        people_data = {
            "person_1": Person(name="Alice"),
            "person_2": Person(name="Bob"),
            "person_3": Person(name="Charlie"),
            "person_4": Person(name="Diana"),
            "person_5": Person(name="Eve"),
        }
        return people_data.get(id)

@api.type(is_root_type=True)
class Root:
    @api.field
    def people(
        self,
        before: Optional[str] = None,
        after: Optional[str] = None,
        first: Optional[int] = None,
        last: Optional[int] = None,
    ) -> PersonConnection:
        """
        Paginated list of people using Relay connection pattern.

        Args:
            before: Cursor to paginate before
            after: Cursor to paginate after
            first: Number of items to fetch from start
            last: Number of items to fetch from end
        """
        # Your data source - in real app, this would be from database
        people_data = collections.OrderedDict([
            ("person_1", Person(name="Alice")),
            ("person_2", Person(name="Bob")),
            ("person_3", Person(name="Charlie")),
            ("person_4", Person(name="Diana")),
            ("person_5", Person(name="Eve")),
        ])

        return PersonConnection(
            people_data,
            before=before,
            after=after,
            first=first,
            last=last
        )

    @api.field
    def person(self, id: str) -> Optional[Person]:
        """Get a person by their global ID."""
        return Person.get_node(None, id)
```

## Database Integration

Integrate Relay pagination with database queries:

```python
class UserConnection(Connection):
    def __init__(self, query_result, total_count, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.users = query_result
        self.total_count = total_count

        # Calculate pagination metadata
        self.has_previous_page = self._after is not None
        self.has_next_page = len(self.users) == (self._first or self._last or 0)

    @api.field
    def edges(self) -> List[Edge]:
        return [
            Edge(cursor=f"user_{user.id}", node=user)
            for user in self.users
        ]

    @api.field
    def page_info(self) -> PageInfo:
        if not self.users:
            return PageInfo(
                start_cursor=None,
                end_cursor=None,
                has_previous_page=False,
                has_next_page=False,
                count=0
            )

        return PageInfo(
            start_cursor=f"user_{self.users[0].id}",
            end_cursor=f"user_{self.users[-1].id}",
            has_previous_page=self.has_previous_page,
            has_next_page=self.has_next_page,
            count=len(self.users)
        )

    @api.field
    def total_count(self) -> int:
        """Total number of items available (not just in current page)."""
        return self.total_count

@api.type(is_root_type=True)
class Root:
    @api.field
    def users(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        last: Optional[int] = None,
        before: Optional[str] = None,
        search: Optional[str] = None
    ) -> UserConnection:
        """
        Paginated user list with search capability.
        """
        # Parse cursor to get offset
        offset = 0
        if after:
            # Extract ID from cursor (e.g., "user_123" -> 123)
            try:
                offset = int(after.split('_')[1])
            except (IndexError, ValueError):
                offset = 0

        # Build database query
        limit = first or last or 20  # Default page size
        if last:
            # For 'last', we need to adjust the query
            pass  # Implement reverse pagination logic

        # Execute database query
        query = db.session.query(User)

        if search:
            query = query.filter(User.name.ilike(f'%{search}%'))

        # Get total count for metadata
        total_count = query.count()

        # Apply pagination
        if after:
            query = query.filter(User.id > offset)

        users = query.order_by(User.id).limit(limit).all()

        return UserConnection(
            query_result=users,
            total_count=total_count,
            first=first,
            after=after,
            last=last,
            before=before
        )
```

## Advanced Pagination Patterns

### Async Database Pagination

```python
class AsyncUserConnection(Connection):
    def __init__(self, users, has_more, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.users = users
        self.has_more = has_more

    @api.field
    def edges(self) -> List[Edge]:
        return [
            Edge(cursor=f"user_{user.id}", node=user)
            for user in self.users
        ]

    @api.field
    def page_info(self) -> PageInfo:
        if not self.users:
            return PageInfo(
                start_cursor=None,
                end_cursor=None,
                has_previous_page=False,
                has_next_page=False,
                count=0
            )

        return PageInfo(
            start_cursor=f"user_{self.users[0].id}",
            end_cursor=f"user_{self.users[-1].id}",
            has_previous_page=self._after is not None,
            has_next_page=self.has_more,
            count=len(self.users)
        )

@api.type(is_root_type=True)
class Root:
    @api.field
    async def async_users(
        self,
        first: Optional[int] = 20,
        after: Optional[str] = None
    ) -> AsyncUserConnection:
        """Async pagination with database."""
        offset = 0
        if after:
            try:
                offset = int(after.split('_')[1])
            except (IndexError, ValueError):
                offset = 0

        # Async database query
        async with get_db_session() as session:
            # Fetch one extra to check if there are more
            limit = first + 1
            users = await session.execute(
                select(User)
                .where(User.id > offset)
                .order_by(User.id)
                .limit(limit)
            )
            users = users.scalars().all()

            # Check if there are more results
            has_more = len(users) > first
            if has_more:
                users = users[:-1]  # Remove the extra item

            return AsyncUserConnection(
                users=users,
                has_more=has_more,
                first=first,
                after=after
            )
```

### Filtering and Sorting with Pagination

```python
from enum import Enum

class SortOrder(Enum):
    ASC = "asc"
    DESC = "desc"

class UserSortField(Enum):
    NAME = "name"
    CREATED_AT = "created_at"
    EMAIL = "email"

@api.type(is_root_type=True)
class Root:
    @api.field
    def filtered_users(
        self,
        first: Optional[int] = 20,
        after: Optional[str] = None,
        filter: Optional[str] = None,
        sort_field: UserSortField = UserSortField.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC
    ) -> UserConnection:
        """
        Advanced pagination with filtering and sorting.
        """
        # Build query with filters
        query = db.session.query(User)

        if filter:
            query = query.filter(
                db.or_(
                    User.name.ilike(f'%{filter}%'),
                    User.email.ilike(f'%{filter}%')
                )
            )

        # Apply sorting
        sort_column = getattr(User, sort_field.value)
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply cursor pagination
        if after:
            # Decode cursor and apply appropriate filter
            cursor_data = decode_cursor(after)
            query = apply_cursor_filter(query, cursor_data, sort_field, sort_order)

        # Execute query
        limit = first + 1  # Get one extra to check for more
        users = query.limit(limit).all()

        has_more = len(users) > first
        if has_more:
            users = users[:-1]

        total_count = query.count()

        return UserConnection(
            query_result=users,
            total_count=total_count,
            first=first,
            after=after
        )
```

## Client Usage Examples

### Basic Pagination Queries

```graphql
# Get first 5 people
query {
  people(first: 5) {
    edges {
      cursor
      node {
        id
        name
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

# Get next page after a cursor
query {
  people(first: 5, after: "person_3") {
    edges {
      cursor
      node {
        id
        name
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}

# Get last 3 people (reverse pagination)
query {
  people(last: 3) {
    edges {
      cursor
      node {
        id
        name
      }
    }
    pageInfo {
      hasPreviousPage
      startCursor
    }
  }
}
```

### Advanced Queries with Filtering

```graphql
# Filtered and sorted pagination
query {
  filteredUsers(
    first: 10,
    filter: "john",
    sortField: NAME,
    sortOrder: ASC
  ) {
    edges {
      node {
        id
        name
        email
        createdAt
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    totalCount
  }
}
```

## Best Practices

**Use stable cursors:**
```python
# ✅ Good: Use stable IDs as cursors
Edge(cursor=f"user_{user.id}", node=user)

# ❌ Avoid: Using array indices as cursors
Edge(cursor=str(index), node=user)  # Unstable when data changes
```

**Implement efficient database queries:**
```python
# ✅ Good: Use database-level pagination
query.offset(offset).limit(limit)

# ❌ Avoid: Loading all data and paginating in memory
all_users = query.all()
paginated = all_users[offset:offset+limit]  # Inefficient for large datasets
```

**Handle edge cases gracefully:**
```python
def safe_cursor_decode(cursor: Optional[str]) -> int:
    """Safely decode cursor with fallback."""
    if not cursor:
        return 0

    try:
        return int(cursor.split('_')[1])
    except (IndexError, ValueError):
        return 0  # Fallback to beginning
```

**Provide helpful metadata:**
```python
@api.field
def enhanced_page_info(self) -> PageInfo:
    return PageInfo(
        start_cursor=self.start_cursor,
        end_cursor=self.end_cursor,
        has_previous_page=self.has_previous_page,
        has_next_page=self.has_next_page,
        count=len(self.current_page),
        total_count=self.total_count,  # Helpful for UI
        page_number=self.calculate_page_number(),  # Helpful for UI
    )
```

Relay pagination provides a robust, standardized approach to handling large datasets in GraphQL APIs, ensuring compatibility with modern GraphQL clients and excellent user experience.