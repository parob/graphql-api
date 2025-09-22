---
title: "Enums and Interfaces"
weight: 7
description: >
  Creating GraphQL enums and interfaces for flexible type definitions
---

# Enums and Interfaces

GraphQL enums and interfaces provide powerful ways to define flexible and extensible schemas. This guide covers how to create and use both in `graphql-api`.

## Enums

Python enums are automatically converted to GraphQL enums, providing type-safe value constraints.

### Basic Enums

Define enums using Python's standard `Enum` class:

```python
import enum

class Episode(enum.Enum):
    NEWHOPE = 4
    EMPIRE = 5
    JEDI = 6

class Status(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

@api.type(is_root_type=True)
class Root:
    @api.field
    def current_episode(self) -> Episode:
        return Episode.EMPIRE

    @api.field
    def user_status(self, user_id: str) -> Status:
        return Status.ACTIVE
```

This generates GraphQL enum types:

```graphql
enum Episode {
  NEWHOPE
  EMPIRE
  JEDI
}

enum Status {
  ACTIVE
  INACTIVE
  PENDING
}

type Query {
  currentEpisode: Episode!
  userStatus(userId: String!): Status!
}
```

### IntEnum Support

Python's `IntEnum` is also supported:

```python
class Priority(enum.IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@api.type(is_root_type=True)
class Root:
    @api.field
    def task_priority(self, priority: Priority) -> str:
        return f"Priority level: {priority.value}"
```

### Enum Values with Descriptions

You can add descriptions to enum values using docstrings:

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

### Advanced Enum Features

For more complex enum scenarios, you can use `EnumValue` for custom metadata:

```python
from graphql_api.schema import EnumValue

class TaskStatus(enum.Enum):
    TODO = EnumValue("todo", description="Task is waiting to be started")
    IN_PROGRESS = EnumValue("in_progress", description="Task is currently being worked on")
    DONE = EnumValue("done", description="Task has been completed")
    BLOCKED = EnumValue("blocked", description="Task is blocked by dependencies")
```

## Interfaces

GraphQL interfaces define contracts that implementing types must follow. Create interfaces by decorating a class with `@api.type(interface=True)`.

### Basic Interfaces

```python
@api.type(interface=True)
class Character:
    """A character in the Star Wars universe."""

    @api.field
    def get_id(self) -> str:
        return "default_id"

    @api.field
    def get_name(self) -> str:
        return "default_name"

    @api.field
    def get_friends(self) -> List['Character']:
        return []

class Human(Character):
    """A human character."""

    def __init__(self, id: str, name: str, home_planet: str):
        self.id = id
        self.name = name
        self.home_planet = home_planet

    @api.field
    def get_id(self) -> str:
        return self.id

    @api.field
    def get_name(self) -> str:
        return self.name

    @api.field
    def home_planet(self) -> str:
        return self.home_planet

class Droid(Character):
    """A droid character."""

    def __init__(self, id: str, name: str, primary_function: str):
        self.id = id
        self.name = name
        self.primary_function = primary_function

    @api.field
    def get_id(self) -> str:
        return self.id

    @api.field
    def get_name(self) -> str:
        return self.name

    @api.field
    def primary_function(self) -> str:
        return self.primary_function
```

This generates GraphQL types with interface implementation:

```graphql
interface Character {
  getId: String!
  getName: String!
  getFriends: [Character!]!
}

type Human implements Character {
  getId: String!
  getName: String!
  getFriends: [Character!]!
  homePlanet: String!
}

type Droid implements Character {
  getId: String!
  getName: String!
  getFriends: [Character!]!
  primaryFunction: String!
}
```

### Interface Inheritance

Classes automatically inherit interface fields when they extend an interface class:

```python
@api.type(interface=True)
class Node:
    """Base interface for objects with global IDs."""

    @api.field
    def get_id(self) -> str:
        """Global object identifier."""
        raise NotImplementedError

class User(Node):
    """A user account."""

    def __init__(self, id: str, name: str, email: str):
        self.id = id
        self.name = name
        self.email = email

    # Implements the Node interface requirement
    @api.field
    def get_id(self) -> str:
        return self.id

    @api.field
    def name(self) -> str:
        return self.name

    @api.field
    def email(self) -> str:
        return self.email
```

**Important**: When a class inherits from an interface, it inherits the actual Python method names (e.g., `get_id`, `get_name`), not the GraphQL field names (e.g., `getId`, `getName`). The interface contract is based on the Python method signatures.

### Querying Interfaces

Clients can query interface fields directly or use inline fragments for implementation-specific fields:

```python
@api.type(is_root_type=True)
class Root:
    @api.field
    def characters(self) -> List[Character]:
        return [
            Human("1", "Luke Skywalker", "Tatooine"),
            Droid("2", "R2-D2", "Astromech")
        ]
```

GraphQL query examples:

```graphql
# Query interface fields
query {
  characters {
    getId
    getName
  }
}

# Query with inline fragments for specific implementations
query {
  characters {
    getId
    getName
    ... on Human {
      homePlanet
    }
    ... on Droid {
      primaryFunction
    }
  }
}
```

### Abstract Base Classes

You can combine interfaces with Python's abstract base classes for stronger type safety:

```python
from abc import ABC, abstractmethod

@api.type(interface=True)
class Searchable(ABC):
    """Interface for searchable entities."""

    @api.field
    @abstractmethod
    def get_search_text(self) -> str:
        """Return searchable text content."""
        pass

    @api.field
    @abstractmethod
    def get_search_tags(self) -> List[str]:
        """Return search tags."""
        pass

class Article(Searchable):
    def __init__(self, title: str, content: str, tags: List[str]):
        self.title = title
        self.content = content
        self.tags = tags

    @api.field
    def get_search_text(self) -> str:
        return f"{self.title} {self.content}"

    @api.field
    def get_search_tags(self) -> List[str]:
        return self.tags

    @api.field
    def title(self) -> str:
        return self.title
```

## Multiple Interface Implementation

A class can implement multiple interfaces:

```python
@api.type(interface=True)
class Timestamped:
    @api.field
    def created_at(self) -> datetime:
        raise NotImplementedError

@api.type(interface=True)
class Taggable:
    @api.field
    def get_tags(self) -> List[str]:
        raise NotImplementedError

class BlogPost(Timestamped, Taggable):
    def __init__(self, title: str, content: str, created_at: datetime, tags: List[str]):
        self.title = title
        self.content = content
        self._created_at = created_at
        self.tags = tags

    @api.field
    def title(self) -> str:
        return self.title

    @api.field
    def content(self) -> str:
        return self.content

    @api.field
    def created_at(self) -> datetime:
        return self._created_at

    @api.field
    def get_tags(self) -> List[str]:
        return self.tags
```

This generates:

```graphql
interface Timestamped {
  createdAt: DateTime!
}

interface Taggable {
  getTags: [String!]!
}

type BlogPost implements Timestamped & Taggable {
  title: String!
  content: String!
  createdAt: DateTime!
  getTags: [String!]!
}
```

## Best Practices

**Use descriptive enum names:**
```python
# ✅ Good: Clear, specific names
class UserRole(enum.Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"

# ❌ Avoid: Generic names
class Type(enum.Enum):
    A = "a"
    B = "b"
```

**Keep interfaces focused:**
```python
# ✅ Good: Single responsibility
@api.type(interface=True)
class Identifiable:
    @api.field
    def get_id(self) -> str:
        pass

# ❌ Avoid: Too many responsibilities
@api.type(interface=True)
class Everything:
    @api.field
    def get_id(self) -> str:
        pass

    @api.field
    def get_name(self) -> str:
        pass

    @api.field
    def process_payment(self) -> bool:
        pass  # Not related to identity
```

**Document interface contracts:**
```python
@api.type(interface=True)
class Cacheable:
    """Interface for objects that can be cached."""

    @api.field
    def cache_key(self) -> str:
        """
        Return a unique cache key for this object.

        The key should be stable and unique across instances.
        """
        raise NotImplementedError
```

**Use enums for constrained values:**
```python
# ✅ Good: Use enums for limited sets of values
class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

# ❌ Avoid: Using strings for constrained values
@api.field
def payment_status(self) -> str:  # Could be any string
    return "pending"
```

Enums and interfaces provide powerful tools for creating flexible, type-safe GraphQL schemas that can evolve over time while maintaining backward compatibility.