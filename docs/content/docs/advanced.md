---
title: "Advanced Topics"
linkTitle: "Advanced"
weight: 8
description: >
  Explore advanced features like middleware, directives, and Relay support
---

# Advanced Topics

This section covers some of the more advanced features of `graphql-api`, including middleware, error handling, resolver context, directives, and Relay support.

## Middleware

Middleware allows you to wrap your resolvers with custom logic, which is useful for tasks like authentication, logging, or performance monitoring.

### Creating Middleware

A middleware is a function that takes the next resolver in the chain and the standard GraphQL resolver arguments (`root`, `info`, and any field arguments).

```python
from typing import Any

def log_middleware(next_, root, info, **args) -> Any:
    """
    A simple middleware to log resolver execution.
    """
    print(f"Executing resolver: {info.field_name}")
    print(f"Arguments: {args}")

    # Call the next middleware or resolver
    result = next_(root, info, **args)

    print(f"Result: {result}")
    return result

def timing_middleware(next_, root, info, **args) -> Any:
    """
    A middleware to measure resolver execution time.
    """
    import time
    start_time = time.time()

    result = next_(root, info, **args)

    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Resolver {info.field_name} took {execution_time:.4f}s")

    return result

def auth_middleware(next_, root, info, **args) -> Any:
    """
    A middleware to check authentication.
    """
    # Check if user is authenticated (example)
    current_user = info.context.get("current_user")
    if not current_user:
        from graphql import GraphQLError
        raise GraphQLError("Authentication required")

    return next_(root, info, **args)
```

### Applying Middleware

You can apply middleware globally when you initialize your API:

```python
from graphql_api.api import GraphQLAPI

# Apply multiple middleware - they execute in order
api = GraphQLAPI(middleware=[auth_middleware, timing_middleware, log_middleware])

@api.type(is_root_type=True)
class Query:
    @api.field
    def protected_data(self) -> str:
        return "Secret information"
```

### Middleware Execution Order

Middleware executes in the order specified in the `middleware` list. Each middleware can:
- Modify arguments before calling the next middleware
- Inspect or modify the result after calling the next middleware
- Handle errors from downstream middleware/resolvers
- Skip calling the next middleware entirely (for early returns)

**Example with context modification:**
```python
def context_middleware(next_, root, info, **args):
    # Add something to context for downstream resolvers
    original_context = info.context
    info.context["request_id"] = "req_123"

    try:
        result = next_(root, info, **args)
        return result
    finally:
        # Clean up if needed
        info.context = original_context
```

When a query is executed, the middleware will be called for each resolved field, providing powerful hooks for cross-cutting concerns.

## Error Handling

Proper error handling is crucial for a robust API. `graphql-api` provides several mechanisms for handling and controlling error behavior.

### Basic Error Handling

By default, `graphql-api` catches exceptions in resolvers and converts them to GraphQL errors:

```python
from typing import Optional

@api.type(is_root_type=True)
class Query:
    @api.field
    def divide(self, a: int, b: int) -> float:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @api.field
    def safe_divide(self, a: int, b: int) -> Optional[float]:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

# Test the behavior
result = api.execute('query { divide(a: 10, b: 0) }')
# result.errors contains the ValueError, result.data is None

result = api.execute('query { safeDivide(a: 10, b: 0) }')
# result.errors contains the ValueError, result.data is {"safeDivide": None}
```

**Key behavior:**
- Errors in **non-null fields** cause the entire query to fail (`data: null`)
- Errors in **nullable fields** return `null` for that field but preserve other data

### Error Protection Control

You can control error protection at the API level or individual field level:

```python
from graphql_api.mapper import GraphQLMetaKey

# Disable error protection globally - exceptions will propagate
api = GraphQLAPI(error_protection=False)

# Or disable for specific fields
@api.type(is_root_type=True)
class Query:
    @api.field({GraphQLMetaKey.error_protection: False})
    def dangerous_operation(self) -> str:
        raise Exception("This will propagate!")

    @api.field  # This field still has error protection
    def safe_operation(self) -> str:
        raise Exception("This becomes a GraphQL error")
```

When `error_protection=False`:
- Exceptions are **not caught** and will propagate to your application
- Useful for debugging or when you want to handle errors at a higher level

### Custom Exception Classes

You can create structured exceptions for better error handling:

```python
from graphql import GraphQLError

class UserNotFoundError(GraphQLError):
    """A specific error for when a user is not found."""
    def __init__(self, user_id: int):
        super().__init__(
            f"User with ID {user_id} not found.",
            extensions={"code": "USER_NOT_FOUND", "user_id": user_id}
        )

class ValidationError(GraphQLError):
    """Error for input validation failures."""
    def __init__(self, field: str, message: str):
        super().__init__(
            f"Validation error on field '{field}': {message}",
            extensions={"code": "VALIDATION_ERROR", "field": field}
        )

@api.type(is_root_type=True)
class Query:
    @api.field
    def get_user_by_id(self, user_id: int) -> User:
        if user_id < 1:
            raise ValidationError("user_id", "Must be positive")

        user = find_user_in_db(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user
```

This provides structured error responses:

```json
{
  "errors": [
    {
      "message": "User with ID 123 not found.",
      "locations": [...],
      "path": ["getUserById"],
      "extensions": {
        "code": "USER_NOT_FOUND",
        "user_id": 123
      }
    }
  ],
  "data": {
    "getUserById": null
  }
}
```

### Partial Error Responses

GraphQL allows partial success - some fields can succeed while others fail:

```python
@api.type(is_root_type=True)
class Query:
    @api.field
    def user_data(self, error: bool = False) -> Optional[str]:
        if error:
            raise Exception("User data failed")
        return "User data loaded"

    @api.field
    def settings_data(self, error: bool = False) -> str:
        if error:
            raise Exception("Settings failed")
        return "Settings loaded"

# Query both fields with mixed success
result = api.execute('''
    query {
        userData(error: false)
        settingsData(error: true)
    }
''')

# Result will have:
# - errors: [exception from settingsData]
# - data: {"userData": "User data loaded", "settingsData": null}
```

This allows clients to handle partial failures gracefully.

## Resolver Context and Meta Information

`graphql-api` provides several ways to access request-specific information and metadata in your resolvers.

### Using GraphQLContext

For structured access to context information, you can use the `GraphQLContext` type annotation:

```python
from graphql_api.context import GraphQLContext

# Custom middleware to inject user context
def auth_middleware(next_, root, info, **args):
    # Simulate authentication - in real app this would check headers/tokens
    info.context.current_user = getattr(info.context, 'current_user', None)
    return next_(root, info, **args)

api = GraphQLAPI(middleware=[auth_middleware])

@api.type(is_root_type=True)
class Query:
    @api.field
    def get_my_profile(self, context: GraphQLContext) -> str:
        # Access custom context data stored as attributes
        current_user = getattr(context, 'current_user', None)
        if not current_user:
            raise PermissionError("You must be logged in")
        return f"Profile for {current_user}"

    @api.field
    def debug_context(self, context: GraphQLContext) -> str:
        # Access field name from request info
        return f"Field: {context.request.info.field_name}"
```

### Populating Context

Context data is typically injected via middleware rather than passed directly to execute:

```python
def context_middleware(next_, root, info, **args):
    # Add request ID to context as an attribute
    info.context.request_id = "req_123"

    # Add database session
    info.context.db_session = create_db_session()

    # Add user from authentication
    info.context.current_user = get_user_from_request()

    # Call next middleware/resolver
    result = next_(root, info, **args)

    # Cleanup if needed
    if hasattr(info.context, 'db_session'):
        info.context.db_session.close()

    return result

api = GraphQLAPI(middleware=[context_middleware])
```

### Meta Information with GraphQLMetaKey

You can access and set metadata on fields and types using `GraphQLMetaKey`:

```python
from graphql_api.mapper import GraphQLMetaKey

@api.type(is_root_type=True)
class Query:
    @api.field({
        GraphQLMetaKey.error_protection: False,
        "custom_meta": "field_metadata"
    })
    def advanced_field(self) -> str:
        return "This field has custom metadata"

    @api.field
    def cached_data(self) -> str:
        # You can access field metadata in resolvers if needed
        return "Expensive computation result"
```

**Available GraphQLMetaKey options:**
- `GraphQLMetaKey.error_protection`: Control error handling for individual fields
- Custom metadata: Add your own metadata for middleware or other processing

### Context in Middleware

Context is particularly useful in middleware for cross-cutting concerns:

```python
def auth_middleware(next_, root, info, **args):
    # Access context in middleware
    context = info.context
    user = getattr(context, "current_user", None)

    if not user and info.field_name in ["protected_field", "admin_data"]:
        from graphql import GraphQLError
        raise GraphQLError("Authentication required")

    # Add computed data to context as attributes
    context.user_permissions = get_user_permissions(user) if user else []

    return next_(root, info, **args)
```

**GraphQLContext Structure:**

The `GraphQLContext` object provides access to:
- `context.schema` - The GraphQL schema
- `context.meta` - Field metadata dictionary
- `context.executor` - The current executor
- `context.request` - Request context with `info` and `args`
  - `context.request.info.field_name` - Current field name
  - `context.request.info.path` - GraphQL path
- `context.field` - Field context with `meta` and `query`
- Custom attributes can be added via middleware using `info.context.attribute_name = value`

Using context and metadata allows you to build sophisticated, secure APIs with clean separation of concerns.

## Directives

`graphql-api` supports custom GraphQL directives, which allow you to add declarative metadata and behavior to your schema elements.

### Built-in Directives

The library provides several built-in directives:

```python
from graphql_api.directives import deprecated

@api.type(is_root_type=True)
class Query:
    @deprecated(reason="Use getNewEndpoint instead")
    @api.field
    def get_old_endpoint(self) -> str:
        return "This endpoint is deprecated"

    @api.field
    def get_new_endpoint(self) -> str:
        return "Use this endpoint instead"
```

### Creating Custom Schema Directives

Use `SchemaDirective` to create custom directives for your schema:

```python
from graphql import DirectiveLocation, GraphQLArgument, GraphQLString
from graphql_api.directives import SchemaDirective
from graphql_api import AppliedDirective

# Define a custom directive
tag = SchemaDirective(
    name="tag",
    locations=[DirectiveLocation.FIELD_DEFINITION, DirectiveLocation.OBJECT],
    args={
        "name": GraphQLArgument(
            GraphQLString,
            description="Tag name"
        )
    },
    description="Tag directive for categorization",
    is_repeatable=True,
)

key = SchemaDirective(
    name="key",
    locations=[DirectiveLocation.OBJECT],
    args={
        "fields": GraphQLArgument(
            GraphQLString,
            description="Key fields for federation"
        )
    },
    description="Federation key directive",
    is_repeatable=True,
)
```

### Applying Directives

There are multiple ways to apply directives:

**1. Decorator syntax:**
```python
@tag(name="auth")
@key(fields="id")
@api.type
class User:
    @api.field
    def id(self) -> str:
        return "user123"

    @tag(name="sensitive")
    @api.field
    def email(self) -> str:
        return "user@example.com"

    @tag(name="profile")
    @api.field(mutable=True)
    def update_name(self, name: str) -> str:
        return f"Updated to {name}"
```

**2. Declarative syntax:**
```python
@api.type(
    directives=[
        AppliedDirective(directive=key, args={"fields": "id"}),
        AppliedDirective(directive=tag, args={"name": "user_type"})
    ]
)
class User:
    @api.field(
        directives=[
            AppliedDirective(directive=tag, args={"name": "identifier"})
        ]
    )
    def id(self) -> str:
        return "user123"
```

### Directive Locations

Directives can be applied to different schema elements:

```python
from graphql import DirectiveLocation

# Object directive
@tag(name="entity")
@api.type
class User:
    pass

# Field directive
@api.type(is_root_type=True)
class Query:
    @tag(name="query_field")
    @api.field
    def get_user(self) -> User:
        return User()

# Interface directive
@tag(name="contract")
@api.type(interface=True)
class Node:
    @api.field
    def id(self) -> str:
        return "node_id"

# Enum directive
import enum
from graphql_api.schema import EnumValue

@tag(name="status_enum")
class Status(enum.Enum):
    ACTIVE = EnumValue("active", tag(name="active_status"))
    INACTIVE = EnumValue("inactive", tag(name="inactive_status"))
```

### Registering Directives

Make sure to register your custom directives with the API:

```python
api = GraphQLAPI(directives=[tag, key])

# Or for global decorators
from graphql_api.decorators import type, field

# Directives registered automatically when used as decorators
@tag(name="global_example")
@type
class Example:
    @field
    def data(self) -> str:
        return "example"
```

### Directive Validation

The library validates directive locations automatically:

```python
# This will raise an error if used incorrectly
object_only_directive = SchemaDirective(
    name="object_only",
    locations=[DirectiveLocation.OBJECT]  # Only for objects
)

# Error: Cannot use @object_only on interface
@object_only_directive  # ❌ This will fail
@api.type(interface=True)
class InvalidInterface:
    pass
```

Directives are powerful tools for adding metadata, federation support, and custom behaviors to your GraphQL schema.

## Schema Filtering and Field Access Control

`graphql-api` provides powerful schema filtering capabilities for controlling field access and schema structure.

### Field-Level Access Control

You can control which fields are available in queries vs mutations:

```python
@api.type(is_root_type=True)
class Root:
    @api.field
    def public_data(self) -> str:
        return "Available in queries"

    @api.field(mutable=True)
    def update_data(self, value: str) -> str:
        return f"Updated: {value}"

# In queries: only public_data is available
# In mutations: both fields may be available depending on context
```

### Schema Validation and Filtering

The library automatically filters invalid field combinations:

```python
class Person:
    @api.field
    def name(self) -> str:
        return "Alice"

    @api.field(mutable=True)
    def update_name(self, name: str) -> str:
        self.name = name
        return name

@api.type(is_root_type=True)
class Query:
    @api.field
    def person(self) -> Person:
        return Person()

# This query will fail - can't use mutation fields in queries
# query { person { updateName(name: "Bob") } }

# This mutation will succeed
# mutation { person { updateName(name: "Bob") } }
```

### Interface and Implementation Filtering

The library maintains proper GraphQL schema structure:

```python
@api.type(interface=True)
class Animal:
    @api.field
    def name(self) -> str:
        return "Generic Animal"

class Dog(Animal):
    @api.field
    def breed(self) -> str:
        return "Golden Retriever"

# Schema filtering ensures interfaces are properly maintained
# Even if some implementations are filtered out
```

## Federation Support

`graphql-api` includes support for Apollo Federation through specialized directives:

```python
from graphql_api.federation.directives import key, link

@key(fields="id")
@api.type
class User:
    @classmethod
    def _resolve_reference(cls, reference):
        # Federation resolver method
        return User(id=reference["id"])

    def __init__(self, id: str):
        self._id = id

    @api.field
    def id(self) -> str:
        return self._id

    @api.field
    def name(self) -> str:
        return "User Name"

@api.type(is_root_type=True)
class Query:
    @api.field
    def user(self, id: str) -> User:
        return User(id=id)

# This creates a federated service that can be composed
# with other GraphQL services
```

**Key federation features:**
- `@key` directive for entity identification
- `_resolve_reference` class method for entity resolution
- Automatic federation schema generation
- Integration with Apollo Gateway

For complete federation examples, see the `test_federation.py` file in the test suite.

## Relay Support

`graphql-api` provides helpers for building Relay-compliant APIs, including support for global object identification and connection-based pagination.

### Node Interface and Global IDs

To enable Relay support, you can use the `Node` interface, which provides a globally unique ID for each object in your schema.

```python
from graphql_api.relay import Node

@api.type
class User(Node):
    # The `id` field is automatically provided by the Node interface
    @api.field
    def name(self) -> str:
        return "John Doe"

    @classmethod
    def get_node(cls, info, id):
        # This method tells Relay how to fetch a User by its global ID
        # In a real app, you would fetch the user from a database
        return User(id=id)
```

### Connection-based Pagination

Relay uses a standardized format for pagination called "Connections." `graphql-api` provides a `Connection` type to simplify the implementation of paginated fields.

For a detailed example of how to implement Relay-compliant pagination, please refer to the `test_relay.py` file in the test suite. This feature allows you to build sophisticated, scalable APIs that integrate seamlessly with modern front-end frameworks like Relay.

## Performance and Best Practices

### Async Resolver Best Practices

When using async resolvers, follow these patterns for optimal performance:

```python
import asyncio
from typing import List

@api.type(is_root_type=True)
class Query:
    @api.field
    async def batch_users(self, ids: List[str]) -> List[User]:
        # Good: Batch multiple async operations
        tasks = [fetch_user_async(id) for id in ids]
        users = await asyncio.gather(*tasks)
        return users

    @api.field
    async def efficient_data(self) -> DataResponse:
        # Good: Use async context managers for resources
        async with get_db_session() as session:
            data = await session.fetch_data()
            return DataResponse(data=data)
```

### Error Handling Best Practices

Structure your error handling for better debugging and client experience:

```python
from graphql import GraphQLError
from typing import Optional

class APIError(GraphQLError):
    """Base class for API errors with structured information."""
    def __init__(self, message: str, code: str, **extensions):
        super().__init__(
            message,
            extensions={"code": code, **extensions}
        )

class ValidationError(APIError):
    def __init__(self, field: str, message: str):
        super().__init__(
            f"Validation failed for {field}: {message}",
            code="VALIDATION_ERROR",
            field=field
        )

@api.type(is_root_type=True)
class Query:
    @api.field
    def process_data(self, input_data: str) -> Optional[str]:
        try:
            # Your processing logic
            if not input_data.strip():
                raise ValidationError("input_data", "Cannot be empty")

            return process_input(input_data)
        except ValidationError:
            raise  # Re-raise validation errors as-is
        except Exception as e:
            # Log unexpected errors for debugging
            logger.exception("Unexpected error in process_data")
            raise APIError(
                "An unexpected error occurred",
                code="INTERNAL_ERROR",
                request_id=get_request_id()
            )
```

### Schema Organization Best Practices

For large applications, organize your schema thoughtfully:

```python
# Separate concerns into modules
# users.py
@api.type
class User:
    @api.field
    def id(self) -> str:
        return self._id

# posts.py
@api.type
class Post:
    @api.field
    def author(self) -> User:
        return User.get_by_id(self.author_id)

# root.py - Bring everything together
@api.type(is_root_type=True)
class Query:
    @api.field
    def user(self, id: str) -> Optional[User]:
        return User.get_by_id(id)

    @api.field
    def posts(self, limit: int = 10) -> List[Post]:
        return Post.get_recent(limit)
```

### Development and Debugging Tips

1. **Use error protection selectively**: Disable for development, enable for production
2. **Add timing middleware**: Monitor resolver performance
3. **Use structured logging**: Include request context in logs
4. **Test with realistic data sizes**: Ensure queries scale properly
5. **Use introspection for debugging**: GraphQL schemas are self-documenting

```python
# Development configuration
if DEBUG:
    api = GraphQLAPI(
        error_protection=False,  # Get full stack traces
        middleware=[timing_middleware, debug_middleware]
    )
else:
    api = GraphQLAPI(
        error_protection=True,   # Hide internal errors
        middleware=[auth_middleware, logging_middleware]
    )
```

These patterns help you build robust, performant GraphQL APIs that scale with your application's needs.