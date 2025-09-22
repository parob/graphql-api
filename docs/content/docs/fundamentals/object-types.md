---
title: "Object Types and Relationships"
weight: 4
description: >
  Creating complex object types, dataclass relationships, and nested data structures
---

# Object Types and Relationships

Learn how to create complex GraphQL object types using dataclasses, Pydantic models, and define relationships between them.

## Basic Object Types

For complex nested data structures, you can define custom object types using dataclasses or Pydantic models:

```python
from dataclasses import dataclass
from pydantic import BaseModel

# Using dataclasses
@dataclass
class Address:
    street: str
    city: str
    country: str

# Using Pydantic models
class User(BaseModel):
    id: int
    name: str
    email: str

@api.type(is_root_type=True)
class Root:
    @api.field
    def user_address(self) -> Address:
        return Address(street="123 Main St", city="New York", country="USA")

    @api.field
    def current_user(self) -> User:
        return User(id=1, name="Alice", email="alice@example.com")
```

Both dataclasses and Pydantic models are automatically converted to GraphQL object types with all their fields exposed.

## Nested Object Relationships

You can create complex nested structures by referencing other types:

```python
@dataclass
class Author:
    id: int
    name: str
    email: str

@dataclass
class Book:
    id: int
    title: str
    isbn: str
    author: Author  # Nested relationship

@api.type(is_root_type=True)
class Query:
    @api.field
    def featured_book(self) -> Book:
        author = Author(id=1, name="Alice Smith", email="alice@example.com")
        return Book(
            id=100,
            title="GraphQL Guide",
            isbn="978-0123456789",
            author=author
        )
```

This creates a GraphQL schema with nested types:

```graphql
type Author {
  id: Int!
  name: String!
  email: String!
}

type Book {
  id: Int!
  title: String!
  isbn: String!
  author: Author!
}

type Query {
  featuredBook: Book!
}
```

## Advanced Dataclass Relationships

For more complex relationships, you can add methods to dataclasses using the standalone `@field` decorator:

```python
from dataclasses import dataclass
from typing import List, Optional
from graphql_api.decorators import field

# Sample data (in real apps, this would be from a database)
authors_db = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"},
]

posts_db = [
    {"id": 1, "title": "First Post", "content": "Content", "author_id": 1},
    {"id": 2, "title": "Second Post", "content": "More content", "author_id": 2},
]

@dataclass
class Post:
    id: int
    title: str
    content: str
    author_id: int

@dataclass
class Author:
    id: int
    name: str
    email: str

    @field
    def get_posts(self) -> List[Post]:
        """Get all posts by this author."""
        return [Post(**p) for p in posts_db if p["author_id"] == self.id]

# Add relationship method to Post after Author is defined
@field
def get_author(self) -> Optional[Author]:
    """Get the author of this post."""
    author_data = next((a for a in authors_db if a["id"] == self.author_id), None)
    if author_data:
        return Author(**author_data)
    return None

# Attach the method to the dataclass
Post.get_author = get_author

@api.type(is_root_type=True)
class Root:
    @api.field
    def posts(self) -> List[Post]:
        return [Post(**p) for p in posts_db]

    @api.field
    def authors(self) -> List[Author]:
        return [Author(**a) for a in authors_db]
```

This creates a GraphQL schema with bi-directional relationships:

```graphql
type Post {
  id: Int!
  title: String!
  content: String!
  authorId: Int!
  getAuthor: Author
}

type Author {
  id: Int!
  name: String!
  email: String!
  getPosts: [Post!]!
}
```

You can now query these relationships:

```graphql
query {
  posts {
    id
    title
    getAuthor {
      name
      email
    }
  }
}

query {
  authors {
    name
    getPosts {
      title
    }
  }
}
```

## Pydantic Model Relationships

Pydantic models can also define complex relationships:

```python
from pydantic import BaseModel
from typing import List, Optional

class Author(BaseModel):
    id: int
    name: str
    bio: Optional[str] = None

class Book(BaseModel):
    id: int
    title: str
    author: Author
    tags: List[str] = []

class Library(BaseModel):
    name: str
    books: List[Book]
    featured_author: Optional[Author] = None

@api.type(is_root_type=True)
class Query:
    @api.field
    def library(self) -> Library:
        author = Author(id=1, name="Jane Doe", bio="Science fiction writer")
        books = [
            Book(
                id=1,
                title="Space Adventures",
                author=author,
                tags=["sci-fi", "adventure"]
            ),
            Book(
                id=2,
                title="Future Worlds",
                author=author,
                tags=["sci-fi", "dystopian"]
            )
        ]
        return Library(
            name="Central Library",
            books=books,
            featured_author=author
        )
```

## Circular References

When dealing with circular references, use forward references with strings:

```python
from __future__ import annotations  # Enable forward references

@dataclass
class Department:
    name: str
    employees: List[Employee]  # Forward reference

@dataclass
class Employee:
    name: str
    department: Department

# This works because Python resolves the types at runtime
```

For more complex cases, you might need to handle circular references manually:

```python
@dataclass
class User:
    id: int
    name: str
    _friends: List[int] = field(default_factory=list)  # Store IDs

    @field
    def friends(self) -> List['User']:
        """Get user's friends as User objects."""
        return [get_user_by_id(friend_id) for friend_id in self._friends]
```

## Lazy Loading and N+1 Prevention

For performance, implement lazy loading in your relationship methods:

```python
@dataclass
class Author:
    id: int
    name: str
    email: str

    @field
    def books(self) -> List[Book]:
        """Get books by this author with efficient loading."""
        # Use batching or caching to prevent N+1 queries
        return book_service.get_books_by_author(self.id)

    @field
    async def books_async(self) -> List[Book]:
        """Async version for better performance."""
        return await book_service.get_books_by_author_async(self.id)
```

## Key Points About Object Relationships

**Using the standalone `@field` decorator:**
- Import from `graphql_api.decorators`
- Methods without `@field` are **not** exposed as GraphQL fields
- You can add methods to dataclasses after definition for complex relationships
- Both sync and async methods are supported
- Docstrings become field descriptions in the schema

**Performance considerations:**
- Be mindful of N+1 query problems
- Use async resolvers for I/O-bound operations
- Consider implementing DataLoader patterns for batching
- Cache expensive computations

**Type safety:**
- Always use proper type hints
- Use `Optional[]` for nullable relationships
- Use `List[]` for one-to-many relationships
- Forward references work for circular dependencies

This gives you the foundation for building complex, interconnected GraphQL schemas with rich object relationships.

## Building on This

Object types work together with other GraphQL features:

**Documentation:** [Documentation](documentation/) shows how to add rich documentation to your object types.

**Data modifications:** [Input Types & Mutations](mutations/) covers handling data modifications for these object types.

**Advanced patterns:** [Enums & Interfaces](enums-interfaces/) introduces polymorphism and advanced type modeling.