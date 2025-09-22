---
title: "Field Types"
weight: 3
description: >
  Complete guide to supported field types and custom scalar types
---

# Field Types

`graphql-api` automatically maps Python types to GraphQL types. Here's a comprehensive overview of supported types:

## Built-in Scalar Types

`graphql-api` supports all standard Python types and automatically maps them to appropriate GraphQL scalars:

```python
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID

@api.type(is_root_type=True)
class Root:
    @api.field
    def string_field(self) -> str:
        return "Hello World"

    @api.field
    def integer_field(self) -> int:
        return 42

    @api.field
    def float_field(self) -> float:
        return 3.14

    @api.field
    def boolean_field(self) -> bool:
        return True

    @api.field
    def uuid_field(self) -> UUID:
        return UUID("12345678-1234-5678-1234-567812345678")

    @api.field
    def datetime_field(self) -> datetime:
        return datetime.now()

    @api.field
    def date_field(self) -> date:
        return date.today()

    @api.field
    def bytes_field(self) -> bytes:
        return b"binary data"
```

**Type Mapping:**
- `str` → `GraphQLString`
- `int` → `GraphQLInt`
- `float` → `GraphQLFloat`
- `bool` → `GraphQLBoolean`
- `UUID` → `GraphQLUUID` (custom scalar)
- `datetime` → `GraphQLDateTime` (custom scalar)
- `date` → `GraphQLDate` (custom scalar)
- `bytes` → `GraphQLBytes` (custom scalar)

## Collection Types

Use Python's typing module for lists and optional values:

```python
from typing import List, Optional

@api.type(is_root_type=True)
class Root:
    @api.field
    def string_list(self) -> List[str]:
        return ["apple", "banana", "cherry"]

    @api.field
    def optional_field(self) -> Optional[str]:
        return None  # Can be null

    @api.field
    def required_field(self) -> str:
        return "Always present"  # Non-null

    @api.field
    def nested_list(self) -> List[List[int]]:
        return [[1, 2], [3, 4]]
```

**GraphQL Output:**
```graphql
type Root {
  stringList: [String!]!
  optionalField: String
  requiredField: String!
  nestedList: [[Int!]!]!
}
```

## JSON and Dynamic Types

For flexible data structures, use the built-in JSON support:

```python
from graphql_api.types import JsonType

@api.type(is_root_type=True)
class Root:
    @api.field
    def dict_field(self) -> dict:
        return {"key": "value", "number": 42}

    @api.field
    def list_field(self) -> list:
        return [1, "mixed", True]

    @api.field
    def json_field(self, data: JsonType) -> JsonType:
        return {"processed": data}
```

The `JsonType` accepts any JSON-serializable Python value: `dict`, `list`, `str`, `int`, `float`, `bool`, or `None`.

**Important note about dict/list return types**: When you return `dict` or `list` objects from fields, they are automatically serialized to JSON strings in the GraphQL response. If you need to return structured objects that clients can query with GraphQL field selection, use dataclasses or Pydantic models instead.

```python
# This returns a JSON string
@api.field
def get_metadata(self) -> dict:
    return {"version": "1.0", "author": "dev"}
# GraphQL response: {"getMetadata": "{\"version\": \"1.0\", \"author\": \"dev\"}"}

# This returns a queryable object
@dataclass
class Metadata:
    version: str
    author: str

@api.field
def get_metadata(self) -> Metadata:
    return Metadata(version="1.0", author="dev")
# GraphQL response: {"getMetadata": {"version": "1.0", "author": "dev"}}
```

## Enum Types

Python enums are automatically converted to GraphQL enums:

```python
import enum

class Status(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class Priority(enum.IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

@api.type(is_root_type=True)
class Root:
    @api.field
    def current_status(self) -> Status:
        return Status.ACTIVE

    @api.field
    def task_priority(self, priority: Priority) -> str:
        return f"Priority level: {priority.value}"
```

## Custom Scalar Types

You can define custom GraphQL scalar types for specialized data handling:

```python
from graphql import GraphQLScalarType, StringValueNode

# Define a custom scalar
def parse_value(value):
    return str(value) + "_parsed"

def parse_literal(node):
    if isinstance(node, StringValueNode):
        return parse_value(node.value)

def serialize(value):
    return str(value) + "_serialized"

GraphQLKey = GraphQLScalarType(
    name="Key",
    description="The `Key` scalar type represents a unique key.",
    serialize=serialize,
    parse_value=parse_value,
    parse_literal=parse_literal,
)

@api.type(is_root_type=True)
class Root:
    @api.field
    def process_key(self, key: GraphQLKey) -> GraphQLKey:  # type: ignore[valid-type]
        return key
```

**Key functions:**
- `serialize`: Converts Python value to GraphQL response format
- `parse_value`: Parses variable values from GraphQL requests
- `parse_literal`: Parses literal values from GraphQL queries

## GraphQL ID Type

For unique identifiers, use the built-in GraphQL ID type:

```python
from graphql import GraphQLID

@api.type(is_root_type=True)
class Root:
    @api.field
    def get_by_id(self, id: GraphQLID) -> str:  # type: ignore[valid-type]
        return f"Found item with ID: {id}"
```

## Union Types

`graphql-api` can create `GraphQLUnionType`s from Python's `typing.Union`. This is useful when a field can return one of several different object types.

```python
from typing import Union

# Assume Cat and Dog are Pydantic models or @api.type classes
class Cat(BaseModel):
    name: str
    meow_volume: int

class Dog(BaseModel):
    name: str
    bark_loudness: int

@api.type(is_root_type=True)
class Root:
    @api.field
    def search_pet(self, name: str) -> Union[Cat, Dog]:
        if name == "Whiskers":
            return Cat(name="Whiskers", meow_volume=10)
        if name == "Fido":
            return Dog(name="Fido", bark_loudness=100)
```

To query a union type, the client must use fragment spreads to specify which fields to retrieve for each possible type:

```graphql
query {
    searchPet(name: "Whiskers") {
        ... on Cat {
            name
            meowVolume
        }
        ... on Dog {
            name
            barkLoudness
        }
    }
}
```

## Object Types

For complex nested data structures, you can define custom object types:

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

### Advanced Dataclass Relationships

For complex object relationships, you can add methods to dataclasses using the standalone `@field` decorator:

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

This creates a GraphQL schema with relationships:

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

Query example:

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
```

**Key Points:**
- Use the standalone `@field` decorator from `graphql_api.decorators`
- Methods without `@field` are **not** exposed as GraphQL fields
- You can add methods to dataclasses after definition for complex relationships
- Both sync and async methods are supported
- Docstrings become field descriptions in the schema

## Input Types

For mutations and complex field arguments, use input types:

```python
from pydantic import BaseModel

class CreateUserInput(BaseModel):
    name: str
    email: str
    age: int

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def create_user(self, input: CreateUserInput) -> User:
        return User(id=999, name=input.name, email=input.email)
```

This generates a GraphQL input type that can be used in mutations:

```graphql
input CreateUserInput {
  name: String!
  email: String!
  age: Int!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
}
```

## See Also

Field types are building blocks for more complex schemas:

**Schema documentation:** [Documentation](documentation/) shows how to add rich documentation and introspection to your schemas.

**Using these types:**
- [Object Types & Relationships](object-types/) - Build complex object structures using these field types
- [Input Types & Mutations](mutations/) - Apply these types in mutations and input validation
- [Custom Directives](directives/) - Add custom behavior to your field types