---
title: "Field Types and Scalars"
weight: 4
description: >
  Complete guide to built-in scalar types, collections, and custom scalar types
---

# Field Types and Scalars

`graphql-api` automatically maps Python types to GraphQL types. This guide covers all supported scalar types and collection types.

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

### Nullability Rules

Understanding GraphQL nullability is crucial:

```python
@api.field
def required_string(self) -> str:
    # GraphQL: String! (non-null)
    return "always has value"

@api.field
def optional_string(self) -> Optional[str]:
    # GraphQL: String (nullable)
    return None

@api.field
def string_list(self) -> List[str]:
    # GraphQL: [String!]! (non-null list of non-null strings)
    return ["a", "b", "c"]

@api.field
def optional_string_list(self) -> Optional[List[str]]:
    # GraphQL: [String!] (nullable list of non-null strings)
    return None
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

This generates GraphQL enum types:

```graphql
enum Status {
  ACTIVE
  INACTIVE
  PENDING
}

enum Priority {
  LOW
  MEDIUM
  HIGH
}
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

The ID type accepts both strings and integers but serializes them as strings in the response.

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

## Type Validation

`graphql-api` performs automatic type validation:

```python
@api.field
def get_number(self) -> int:
    return "not a number"  # This will cause a runtime error
```

Always ensure your resolver return types match your type hints for predictable behavior.

This covers all the basic scalar and collection types. Next, you'll learn about creating complex object types and relationships.