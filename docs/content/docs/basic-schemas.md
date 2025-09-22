---
title: "Basic Schema Definition"
weight: 3
description: >
  Learn the fundamentals of defining GraphQL schemas with decorator patterns and modes
---

# Basic Schema Definition

This guide covers the core concepts of defining GraphQL schemas using `graphql-api`, including decorator patterns and schema definition modes.

## Decorator Patterns

There are two main patterns for using the `@api.field` and `@api.type` decorators. Choose the pattern that best fits your project structure.

### 1. Instance Decorators (Recommended)

The recommended approach is to create an API instance and use its decorators:

```python
from graphql_api.api import GraphQLAPI

# Create your API instance
api = GraphQLAPI()

# Use the instance decorators
@api.type(is_root_type=True)
class Query:
    @api.field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

# Execute queries
result = api.execute('query { hello }')
```

**Benefits:**
- Clear ownership of types and fields
- Easy to manage multiple APIs
- Explicit and readable
- Recommended for most use cases

### 2. Global Decorators (Use only when necessary)

You can also import decorators globally, but this is only recommended for simple cases:

```python
from graphql_api import field, type, GraphQLAPI

@type(is_root_type=True)
class Query:
    @field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

# You still need to create an API instance to execute
api = GraphQLAPI()
result = api.execute('query { hello }')
```

**Use only when:**
- You have a single, simple API
- You want to minimize imports
- You're prototyping

## Choosing Between Patterns

### Instance Decorators for Most Cases

```python
# ✅ Recommended: Clear and explicit
api = GraphQLAPI()

@api.type(is_root_type=True)
class Query:
    @api.field
    def books(self) -> List[Book]:
        return get_books()
```

### Circular Import Considerations

If you encounter circular imports with instance decorators, you have several options:

**Option 1: Use global decorators temporarily**
```python
from graphql_api import field, type

@type
class Author:
    @field
    def books(self) -> List['Book']:  # Forward reference
        return get_books_by_author(self.id)
```

**Option 2: Restructure your modules**
```python
# models.py
from api_instance import api

@api.type
class Author:
    # ...

# api_instance.py
from graphql_api.api import GraphQLAPI
api = GraphQLAPI()
```

## Schema Definition Modes

`graphql-api` supports two modes for organizing your GraphQL schema. Mode 1 is strongly recommended for most applications.

### Mode 1: Single Root Type (Strongly Recommended)

In Mode 1, you define one class that serves as both Query and Mutation root:

```python
api = GraphQLAPI()

@api.type(is_root_type=True)
class Root:
    # Query fields
    @api.field
    def hello(self) -> str:
        return "Hello World"

    @api.field
    def books(self) -> List[Book]:
        return get_all_books()

    # Mutation fields (marked with mutable=True)
    @api.field(mutable=True)
    def create_book(self, title: str, author: str) -> Book:
        return create_new_book(title, author)

    @api.field(mutable=True)
    def update_book(self, id: str, title: str) -> Book:
        return update_existing_book(id, title)

# Execute queries and mutations
query_result = api.execute('query { hello books { title } }')
mutation_result = api.execute('mutation { createBook(title: "New Book", author: "Author") { id } }')
```

**Benefits of Mode 1:**
- **Natural organization**: All your resolvers in one place
- **Feels like a normal application**: Similar to REST controllers or service classes
- **Easy to understand**: Clear single entry point
- **Simpler imports**: Everything in one class
- **Better IDE support**: Autocomplete and refactoring work better

### Mode 2: Explicit Types

In Mode 2, you define separate Query and Mutation classes:

```python
api = GraphQLAPI()

@api.type
class Query:
    @api.field
    def hello(self) -> str:
        return "Hello World"

    @api.field
    def books(self) -> List[Book]:
        return get_all_books()

@api.type
class Mutation:
    @api.field
    def create_book(self, title: str, author: str) -> Book:
        return create_new_book(title, author)

    @api.field
    def update_book(self, id: str, title: str) -> Book:
        return update_existing_book(id, title)

# Assign the types to the API
api.query_type = Query
api.mutation_type = Mutation

# Execute queries and mutations
query_result = api.execute('query { hello books { title } }')
mutation_result = api.execute('mutation { createBook(title: "New Book", author: "Author") { id } }')
```

**Use Mode 2 when:**
- You have a large API with many operations
- You want strict separation between queries and mutations
- You're migrating from another GraphQL library
- Your team prefers explicit type separation

### Choosing the Right Mode

**Use Mode 1 (Single Root Type) when:**
- ✅ Starting a new project
- ✅ You want the simplest setup
- ✅ Your API is small to medium-sized
- ✅ You prefer a service-class style organization

**Use Mode 2 (Explicit Types) when:**
- 🔄 You have a very large API
- 🔄 You need strict query/mutation separation
- 🔄 Multiple teams work on different parts
- 🔄 You're following GraphQL schema-first patterns

## Core Concepts

### Automatic Schema Generation

`graphql-api` automatically generates your GraphQL schema from Python type hints:

```python
@api.type(is_root_type=True)
class Query:
    @api.field
    def user(self, id: str) -> Optional[User]:
        """Get a user by ID. Returns None if not found."""
        return find_user(id)

    @api.field
    def users(self, limit: int = 10) -> List[User]:
        """Get a list of users with optional limit."""
        return get_users(limit)
```

This generates the following GraphQL schema:

```graphql
type Query {
  user(id: String!): User
  users(limit: Int = 10): [User!]!
}
```

### Type Safety

Type hints provide compile-time and runtime safety:

```python
@api.field
def get_user_age(self, user_id: str) -> int:
    user = find_user(user_id)
    if user is None:
        raise ValueError("User not found")
    return user.age  # Type checker knows this is int
```

### Field Configuration

You can configure fields with metadata:

```python
@api.field({
    "description": "Custom field description",
    "deprecation_reason": "Use newField instead"
})
def old_field(self) -> str:
    return "deprecated value"
```

This foundation gives you everything you need to start building GraphQL APIs. Next, you'll learn about the various field types you can use in your schema.