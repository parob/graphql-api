---
title: "Schema Documentation"
weight: 1
description: >
  Automatic schema documentation with Python docstrings and description generation
---

# Schema Documentation

`graphql-api` automatically converts Python docstrings into GraphQL schema descriptions, making your API self-documenting and providing rich information for GraphQL introspection tools.

## Basic Docstring Usage

Python docstrings are automatically converted to GraphQL descriptions:

```python
@api.type(is_root_type=True)
class Query:
    """
    The root query type for our API.
    This docstring becomes the type description.
    """

    @api.field
    def get_user(self, user_id: str) -> str:
        """
        Retrieve a user by their unique ID.

        This docstring becomes the field description in the GraphQL schema.
        """
        return f"User {user_id}"

    @api.field
    def search_users(self, query: str, limit: int = 10) -> List[str]:
        """Search for users matching a query string."""
        return [f"User matching '{query}'"]
```

This generates GraphQL schema with descriptions:

```graphql
"""
The root query type for our API.
This docstring becomes the type description.
"""
type Query {
  """
  Retrieve a user by their unique ID.

  This docstring becomes the field description in the GraphQL schema.
  """
  getUser(userId: String!): String!

  """Search for users matching a query string."""
  searchUsers(query: String!, limit: Int = 10): [String!]!
}
```

## Dataclass Documentation

Docstrings work seamlessly with dataclasses and their fields:

```python
from dataclasses import dataclass

@dataclass
class User:
    """Represents a user in the system."""
    id: str
    """The unique identifier for the user."""
    name: str
    """The user's display name."""
    email: str
    """The user's email address."""
    age: Optional[int] = None
    """The user's age in years."""

@api.type(is_root_type=True)
class Query:
    @api.field
    def user(self) -> User:
        """Get the current user information."""
        return User(
            id="123",
            name="Alice",
            email="alice@example.com",
            age=30
        )
```

This creates a documented GraphQL type:

```graphql
"""Represents a user in the system."""
type User {
  """The unique identifier for the user."""
  id: String!

  """The user's display name."""
  name: String!

  """The user's email address."""
  email: String!

  """The user's age in years."""
  age: Int
}

type Query {
  """Get the current user information."""
  user: User!
}
```

## Pydantic Model Documentation

Pydantic models also support automatic documentation extraction:

```python
from pydantic import BaseModel, Field

class CreateUserInput(BaseModel):
    """Input data for creating a new user account."""

    name: str = Field(description="The user's full name")
    email: str = Field(description="Valid email address")
    age: Optional[int] = Field(description="Age in years", ge=0, le=150)

class User(BaseModel):
    """A user account in the system."""
    id: str
    name: str
    email: str
    created_at: datetime

@api.type(is_root_type=True)
class Query:
    @api.field(mutable=True)
    def create_user(self, input: CreateUserInput) -> User:
        """Create a new user account with the provided information."""
        # Implementation here
        pass
```

## Advanced Docstring Parsing

The library supports Google-style docstrings for more structured documentation:

```python
@dataclass
class Product:
    """
    A product in our catalog.

    Args:
        id: The unique product identifier
        name: The product display name
        price: The product price in cents
        category: The product category name
        tags: List of product tags for search
    """
    id: str
    name: str
    price: int
    category: str
    tags: List[str]

@api.type(is_root_type=True)
class Query:
    @api.field
    def product(self, product_id: str) -> Optional[Product]:
        """
        Retrieve a product by its ID.

        Args:
            product_id: The unique identifier for the product

        Returns:
            The product if found, None otherwise

        Raises:
            ValidationError: If the product_id format is invalid
        """
        return find_product(product_id)
```

The Args section in the docstring is parsed and used to provide field descriptions.

## Enum Documentation

Enums also support documentation:

```python
class OrderStatus(enum.Enum):
    """The current status of an order."""
    PENDING = "pending"
    """Order has been created but not yet processed."""

    PROCESSING = "processing"
    """Order is currently being processed."""

    SHIPPED = "shipped"
    """Order has been shipped to the customer."""

    DELIVERED = "delivered"
    """Order has been successfully delivered."""

    CANCELLED = "cancelled"
    """Order was cancelled before completion."""
```

## Method Documentation with @field Decorator

When using the standalone `@field` decorator for relationships, docstrings are preserved:

```python
from graphql_api.decorators import field

@dataclass
class Author:
    id: int
    name: str

    @field
    def get_books(self) -> List[Book]:
        """
        Retrieve all books written by this author.

        Returns a list of books ordered by publication date.
        """
        return Book.find_by_author(self.id)
```

## Automatic Features

**What gets documented automatically:**
- ✅ Class docstrings become GraphQL type descriptions
- ✅ Method docstrings become field descriptions
- ✅ Dataclass field docstrings are extracted
- ✅ Google-style Args sections are parsed for field descriptions
- ✅ Pydantic model docstrings are preserved
- ✅ Pydantic Field descriptions are used
- ✅ Enum value docstrings become enum value descriptions
- ✅ Default Pydantic docstrings are filtered out

**Docstring Processing:**
- Multi-line docstrings are properly formatted
- Leading/trailing whitespace is cleaned up
- Google-style sections (Args, Returns, Raises) are parsed
- Markdown formatting is preserved

## Documentation in GraphQL Tools

These descriptions appear in:

- **GraphQL introspection queries** - Available via `__schema` and `__type` queries
- **GraphiQL and GraphQL Playground** - Interactive documentation sidebar
- **Apollo Studio** - Schema documentation and explorer
- **Generated client code** - Type definitions include descriptions
- **API documentation generators** - Tools like GraphQL Doctor

## Best Practices

**Write clear, concise descriptions:**
```python
@api.field
def user_profile(self, user_id: str) -> UserProfile:
    """Get detailed profile information for a specific user."""
    pass
```

**Include parameter information:**
```python
@api.field
def search_products(self, query: str, category: Optional[str] = None) -> List[Product]:
    """
    Search for products in the catalog.

    Args:
        query: Search terms to match against product names and descriptions
        category: Optional category filter to narrow results
    """
    pass
```

**Document edge cases and behavior:**
```python
@api.field
def user_orders(self, user_id: str, limit: int = 10) -> List[Order]:
    """
    Retrieve recent orders for a user.

    Returns orders sorted by creation date (newest first).
    Maximum limit is 100 orders per request.
    """
    pass
```

This automatic documentation feature makes your GraphQL API self-describing and significantly improves the developer experience for API consumers.