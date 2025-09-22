---
title: "API Reference"
weight: 2
description: >
  Complete API reference for graphql-api
---

# API Reference

Complete reference for all classes, methods, and decorators in `graphql-api`.

## Table of Contents

- [GraphQLAPI](#graphqlapi)
- [Decorators](#decorators)
- [Types and Utilities](#types-and-utilities)
- [Error Handling](#error-handling)
- [Federation](#federation)
- [Middleware](#middleware)

---

## GraphQLAPI

The main class for creating GraphQL APIs.

### Constructor

```python
class GraphQLAPI:
    def __init__(
        self,
        root_type: Optional[Type] = None,
        query_type: Optional[Type] = None,
        mutation_type: Optional[Type] = None,
        subscription_type: Optional[Type] = None,
        directives: Optional[List[GraphQLDirective]] = None,
        middleware: Optional[List[Middleware]] = None,
        **kwargs
    ) -> None
```

**Parameters:**
- `root_type`: Single root type containing all operations (Mode 1 - Single Root Type)
- `query_type`: Explicit query type class (Mode 2 - Explicit Types)
- `mutation_type`: Explicit mutation type class (Mode 2 - Explicit Types)
- `subscription_type`: Explicit subscription type class (Mode 2 - Explicit Types)
- `directives`: List of custom GraphQL directives
- `middleware`: List of middleware classes

**Note:** Cannot mix root_type with explicit types (query_type, mutation_type, subscription_type). See [Schema Definition Modes](../defining-schemas/#schema-definition-modes) for more details.

### Methods

#### `execute(query, variables=None, context_value=None, root_value=None)`

Execute a GraphQL query.

```python
def execute(
    self,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    context_value: Optional[Any] = None,
    root_value: Optional[Any] = None
) -> GraphQLResult
```

**Parameters:**
- `query`: GraphQL query string
- `variables`: Variables for the query
- `context_value`: Context object passed to resolvers
- `root_value`: Root value for execution

**Returns:** `GraphQLResult` with `data` and `errors` attributes.

#### `execute_async(query, variables=None, context_value=None, root_value=None)`

Execute a GraphQL query asynchronously.

```python
async def execute_async(
    self,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    context_value: Optional[Any] = None,
    root_value: Optional[Any] = None
) -> GraphQLResult
```

#### `subscribe(query, variables=None, context_value=None, root_value=None)`

Execute a GraphQL subscription.

```python
async def subscribe(
    self,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    context_value: Optional[Any] = None,
    root_value: Optional[Any] = None
) -> AsyncGenerator[GraphQLResult, None]
```

#### `build_schema()`

Build the GraphQL schema from decorated types.

```python
def build_schema(self) -> Tuple[GraphQLSchema, SchemaMeta]
```

**Returns:** Tuple of GraphQL schema and metadata.

#### `get_schema_sdl()`

Get the Schema Definition Language representation.

```python
def get_schema_sdl(self) -> str
```

**Returns:** SDL string representation of the schema.

---

## Decorators

### `@api.type`

Mark a class as a GraphQL type.

```python
@api.type(
    is_root_type: bool = False,
    name: Optional[str] = None,
    description: Optional[str] = None
)
```

**Parameters:**
- `is_root_type`: Whether this is the root type for unified schema approach
- `name`: Custom name for the GraphQL type (defaults to class name)
- `description`: Description for the type

**Example:**
```python
@api.type
class User:
    pass

@api.type(is_root_type=True)
class RootAPI:
    pass
```

### `@api.field`

Mark a method as a GraphQL field.

```python
@api.field(
    mutable: bool = False,
    subscription: bool = False,
    name: Optional[str] = None,
    description: Optional[str] = None,
    deprecation_reason: Optional[str] = None
)
```

**Parameters:**
- `mutable`: If True, field goes in Mutation type (unified approach only)
- `subscription`: If True, field goes in Subscription type (unified approach only)
- `name`: Custom field name (defaults to method name)
- `description`: Field description
- `deprecation_reason`: Deprecation notice

**Example:**
```python
@api.field
def get_user(self, user_id: int) -> User:
    pass

@api.field(mutable=True)
def create_user(self, name: str) -> User:
    pass

@api.field(subscription=True)
async def user_updates(self) -> AsyncGenerator[User, None]:
    pass
```


### `@api.enum`

Mark an enum class as a GraphQL enum.

```python
@api.enum(
    name: Optional[str] = None,
    description: Optional[str] = None
)
```

**Example:**
```python
from enum import Enum

@api.enum
class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
```

### `@api.interface`

Mark a class as a GraphQL interface.

```python
@api.interface(
    name: Optional[str] = None,
    description: Optional[str] = None
)
```

**Example:**
```python
@api.interface
class Node:
    @api.field
    def id(self) -> str:
        pass
```

### `@api.union`

Create a GraphQL union type.

```python
@api.union(types: List[Type], name: str, description: Optional[str] = None)
```

**Example:**
```python
@api.union([User, Admin], "Person")
class PersonUnion:
    pass
```

---

## Types and Utilities

### GraphQLResult

Result object returned by query execution.

```python
class GraphQLResult:
    data: Optional[Dict[str, Any]]
    errors: Optional[List[GraphQLError]]
```

### SchemaMeta

Metadata about the built schema.

```python
class SchemaMeta:
    query_type: Optional[GraphQLObjectType]
    mutation_type: Optional[GraphQLObjectType]
    subscription_type: Optional[GraphQLObjectType]
    types: Dict[str, GraphQLType]
```

### Type Mapping

GraphQL API automatically maps Python types to GraphQL types:

| Python Type | GraphQL Type |
|-------------|--------------|
| `str` | `String` |
| `int` | `Int` |
| `float` | `Float` |
| `bool` | `Boolean` |
| `datetime` | `DateTime` (custom scalar) |
| `List[T]` | `[T]` |
| `Optional[T]` | `T` (nullable) |
| `Dict[str, Any]` | `JSON` (custom scalar) |
| Pydantic models | Object types |
| Dataclasses | Object types |
| Enums | Enum types |

---

## Error Handling

### GraphQLError

Exception class for GraphQL errors.

```python
class GraphQLError(Exception):
    def __init__(
        self,
        message: str,
        locations: Optional[List[SourceLocation]] = None,
        path: Optional[List[Union[str, int]]] = None,
        extensions: Optional[Dict[str, Any]] = None
    )
```

**Example:**
```python
from graphql_api.error import GraphQLError

@api.field
def get_user(self, user_id: int) -> User:
    user = find_user(user_id)
    if not user:
        raise GraphQLError(f"User {user_id} not found")
    return user
```

---

## Federation

### Federation Decorators

#### `@api.key`

Mark a type as a federated entity.

```python
@api.key(fields: str)
```

**Example:**
```python
@api.type
@api.key("id")
class User:
    id: str
    name: str
```

#### `@api.external`

Mark a field as external (resolved by another service).

```python
@api.external
```

#### `@api.requires`

Specify required fields for a resolver.

```python
@api.requires(fields: str)
```

#### `@api.provides`

Specify fields provided by a resolver.

```python
@api.provides(fields: str)
```

#### `@api.extends`

Extend a type from another service.

```python
@api.extends
```

### Federation Schema

```python
def build_federation_schema(api: GraphQLAPI) -> str:
    """Build a federation-compatible SDL."""
```

---

## Middleware

### Middleware Interface

```python
class Middleware:
    def resolve(
        self,
        next_resolver: Callable,
        root: Any,
        info: GraphQLResolveInfo,
        **kwargs
    ) -> Any:
        """Process the resolver call."""
        pass
```

### Built-in Middleware

#### LoggingMiddleware

```python
from graphql_api.middleware import LoggingMiddleware

api = GraphQLAPI(middleware=[LoggingMiddleware()])
```

#### AuthenticationMiddleware

```python
from graphql_api.middleware import AuthenticationMiddleware

class CustomAuthMiddleware(AuthenticationMiddleware):
    def authenticate(self, context: Any) -> bool:
        return context.user is not None
```

#### CacheMiddleware

```python
from graphql_api.middleware import CacheMiddleware

api = GraphQLAPI(middleware=[CacheMiddleware(ttl=300)])
```

---

## Advanced Features

### Custom Scalars

```python
from graphql import GraphQLScalarType

@api.scalar
class DateTimeScalar(GraphQLScalarType):
    name = "DateTime"
    # Implementation details...
```

### Directives

```python
from graphql import GraphQLDirective, GraphQLArgument

@api.directive
class DeprecatedDirective(GraphQLDirective):
    name = "deprecated"
    locations = [DirectiveLocation.FIELD_DEFINITION]
    args = {
        "reason": GraphQLArgument(GraphQLString)
    }
```

### Context and Info

Access request context and GraphQL execution info in resolvers:

```python
from graphql import GraphQLResolveInfo

@api.field
def protected_field(self, info: GraphQLResolveInfo) -> str:
    context = info.context
    if not context.user.is_authenticated:
        raise GraphQLError("Authentication required")
    return "Protected data"
```

### Relay Support

```python
from graphql_api.relay import Node, connection_field

@api.type
class User(Node):
    @api.field
    def id(self) -> str:
        return self.global_id

    @connection_field
    def posts(self) -> Connection[Post]:
        return self.get_posts_connection()
```

---

## Configuration Options

### Schema Configuration

```python
api = GraphQLAPI(
    # Disable introspection in production
    introspection=False,

    # Custom schema directives
    directives=[custom_directive],

    # Type extensions
    type_extensions={
        "Query": ["extend type Query { version: String }"]
    },

    # Validation rules
    validation_rules=[custom_validation_rule]
)
```

### Execution Options

```python
result = api.execute(
    query,
    # Execution timeout
    timeout=30,

    # Maximum query depth
    max_depth=10,

    # Query complexity analysis
    max_complexity=1000
)
```