---
title: "Directives"
weight: 1
description: >
  Creating and using custom GraphQL directives for declarative schema metadata
---

# Directives

GraphQL directives provide a way to add declarative metadata and behavior to your schema elements. `graphql-api` supports both built-in and custom directives, allowing you to enhance your schema with powerful capabilities like deprecation notices, federation support, and custom behaviors.

## Understanding Directives

Directives are like annotations that you can attach to various parts of your GraphQL schema:
- Types and interfaces
- Fields and arguments
- Enum values
- Input types and input fields

They provide metadata that can be used by:
- GraphQL tools and clients
- Federation gateways
- Custom middleware and resolvers
- Schema validation and transformation

## Built-in Directives

### Deprecation Directive

Mark fields or enum values as deprecated:

```python
from graphql_api.directives import deprecated

@api.type(is_root_type=True)
class Root:
    @deprecated(reason="Use getNewEndpoint instead")
    @api.field
    def get_old_endpoint(self) -> str:
        return "This endpoint is deprecated"

    @api.field
    def get_new_endpoint(self) -> str:
        return "Use this endpoint instead"

    @deprecated(reason="Use getUserById instead")
    @api.field
    def get_user(self, name: str) -> str:
        return f"User: {name}"

    @api.field
    def get_user_by_id(self, id: str) -> str:
        return f"User with ID: {id}"
```

This generates GraphQL schema with deprecation information:

```graphql
type Query {
  getOldEndpoint: String! @deprecated(reason: "Use getNewEndpoint instead")
  getNewEndpoint: String!
  getUser(name: String!): String! @deprecated(reason: "Use getUserById instead")
  getUserById(id: String!): String!
}
```

### Standard GraphQL Directives

All standard GraphQL directives are supported:
- `@deprecated` - Mark fields as deprecated
- `@skip` - Conditionally skip fields (client-side)
- `@include` - Conditionally include fields (client-side)

## Creating Custom Schema Directives

Use `SchemaDirective` to create custom directives for your schema:

```python
from graphql import DirectiveLocation, GraphQLArgument, GraphQLString, GraphQLBoolean
from graphql_api.directives import SchemaDirective
from graphql_api import AppliedDirective

# Define a tagging directive
tag = SchemaDirective(
    name="tag",
    locations=[
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.OBJECT,
        DirectiveLocation.INTERFACE,
        DirectiveLocation.ENUM_VALUE
    ],
    args={
        "name": GraphQLArgument(
            GraphQLString,
            description="Tag name for categorization"
        )
    },
    description="Tag directive for categorizing schema elements",
    is_repeatable=True,  # Allow multiple @tag directives
)

# Define a caching directive
cache = SchemaDirective(
    name="cache",
    locations=[DirectiveLocation.FIELD_DEFINITION],
    args={
        "ttl": GraphQLArgument(
            GraphQLString,
            description="Time to live in seconds"
        ),
        "enabled": GraphQLArgument(
            GraphQLBoolean,
            default_value=True,
            description="Whether caching is enabled"
        )
    },
    description="Caching configuration for fields"
)

# Define a permission directive
requires_permission = SchemaDirective(
    name="requiresPermission",
    locations=[DirectiveLocation.FIELD_DEFINITION],
    args={
        "permission": GraphQLArgument(
            GraphQLString,
            description="Required permission level"
        )
    },
    description="Permission requirement for field access"
)
```

## Applying Directives

There are multiple ways to apply directives to your schema elements:

### 1. Decorator Syntax (Recommended)

```python
@tag(name="entity")
@api.type
class User:
    @tag(name="identifier")
    @api.field
    def id(self) -> str:
        return "user123"

    @tag(name="sensitive")
    @requires_permission(permission="read_user_email")
    @cache(ttl="300", enabled=True)
    @api.field
    def email(self) -> str:
        return "user@example.com"

    @tag(name="profile")
    @cache(ttl="60")
    @api.field
    def name(self) -> str:
        return "John Doe"

    @tag(name="mutation")
    @requires_permission(permission="update_user")
    @api.field(mutable=True)
    def update_name(self, name: str) -> str:
        return f"Updated to {name}"
```

### 2. Declarative Syntax

```python
@api.type(
    directives=[
        AppliedDirective(directive=tag, args={"name": "user_type"}),
        AppliedDirective(directive=cache, args={"ttl": "3600"})
    ]
)
class User:
    @api.field(
        directives=[
            AppliedDirective(directive=tag, args={"name": "identifier"}),
            AppliedDirective(directive=requires_permission, args={"permission": "read_user_id"})
        ]
    )
    def id(self) -> str:
        return "user123"

    @api.field(
        directives=[
            AppliedDirective(directive=cache, args={"ttl": "300", "enabled": True})
        ]
    )
    def profile_data(self) -> str:
        return "Profile information"
```

### 3. Multiple Directives

Since some directives are repeatable, you can apply them multiple times:

```python
@tag(name="entity")
@tag(name="user")
@tag(name="authenticated")
@api.type
class User:
    @tag(name="public")
    @tag(name="identifier")
    @cache(ttl="3600")
    @api.field
    def id(self) -> str:
        return "user123"
```

## Directive Locations

Directives can be applied to different schema elements based on their defined locations:

```python
from graphql import DirectiveLocation

# Object directive
@tag(name="entity")
@api.type
class User:
    pass

# Field directive
@api.type(is_root_type=True)
class Root:
    @tag(name="query_field")
    @cache(ttl="60")
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
    ACTIVE = EnumValue("active", directives=[
        AppliedDirective(directive=tag, args={"name": "active_status"})
    ])
    INACTIVE = EnumValue("inactive", directives=[
        AppliedDirective(directive=tag, args={"name": "inactive_status"})
    ])

# Alternative enum syntax
@tag(name="priority_enum")
class Priority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

## Argument Directives

Directives can also be applied to field arguments using Python's `Annotated` type hint:

```python
from typing import Annotated
from graphql import DirectiveLocation, GraphQLArgument, GraphQLString, GraphQLInt
from graphql_api.directives import SchemaDirective

# Define a constraint directive for arguments
constraint = SchemaDirective(
    name="constraint",
    locations=[DirectiveLocation.ARGUMENT_DEFINITION],
    args={
        "min": GraphQLArgument(GraphQLInt, description="Minimum value"),
        "max": GraphQLArgument(GraphQLInt, description="Maximum value"),
        "pattern": GraphQLArgument(GraphQLString, description="Regex pattern"),
    },
    description="Validation constraints for arguments"
)

# Define a directive without arguments
sensitive = SchemaDirective(
    name="sensitive",
    locations=[DirectiveLocation.ARGUMENT_DEFINITION],
    description="Marks argument as containing sensitive data"
)

@api.type(is_root_type=True)
class Root:
    @api.field
    def search(
        self,
        # Shorthand syntax with arguments
        query: Annotated[str, constraint(min=1, max=100)],
        # Shorthand syntax without arguments (no parentheses needed)
        password: Annotated[str, sensitive],
        # Multiple directives on one argument
        limit: Annotated[int, constraint(min=1, max=50), sensitive] = 10
    ) -> str:
        return f"Searching for: {query}"
```

This generates the following schema:

```graphql
type Query {
  search(
    query: String! @constraint(min: 1, max: 100)
    password: String! @sensitive
    limit: Int = 10 @constraint(min: 1, max: 50) @sensitive
  ): String!
}
```

### Argument Directive Syntax Options

There are three ways to apply directives to arguments:

```python
from typing import Annotated
from graphql_api import AppliedDirective

@api.field
def example(
    self,
    # 1. Shorthand with args - most concise
    arg1: Annotated[str, constraint(max=100)],

    # 2. Shorthand without args - for directives with no arguments
    arg2: Annotated[str, sensitive],

    # 3. Explicit AppliedDirective - verbose but flexible
    arg3: Annotated[str, AppliedDirective(directive=constraint, args={"max": 50})],
) -> str:
    return "example"
```

### Using Built-in Directives on Arguments

You can use the built-in `deprecated` directive on arguments:

```python
from graphql_api.directives import deprecated

@api.type(is_root_type=True)
class Root:
    @api.field
    def get_user(
        self,
        id: str,
        # Mark old parameter as deprecated
        name: Annotated[str, deprecated(reason="Use id parameter instead")] = ""
    ) -> str:
        return f"User: {id or name}"
```

## Registering Directives

Make sure to register your custom directives with the API:

```python
# Register with API instance
api = GraphQLAPI(directives=[tag, cache, requires_permission])

# Or for global decorators (automatically registered when used)
from graphql_api.decorators import type, field

@tag(name="global_example")
@type
class Example:
    @cache(ttl="120")
    @field
    def data(self) -> str:
        return "example"
```

## Advanced Directive Patterns

### Federation Directives

Create directives for Apollo Federation:

```python
# Federation key directive
key = SchemaDirective(
    name="key",
    locations=[DirectiveLocation.OBJECT, DirectiveLocation.INTERFACE],
    args={
        "fields": GraphQLArgument(
            GraphQLString,
            description="Key fields for federation"
        )
    },
    description="Federation key directive",
    is_repeatable=True,
)

# External directive for federated fields
external = SchemaDirective(
    name="external",
    locations=[DirectiveLocation.FIELD_DEFINITION],
    description="Mark field as external in federation"
)

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

    @external
    @api.field
    def email(self) -> str:
        # This field is provided by another service
        return "user@example.com"
```

### Validation Directives

Create directives for input validation:

```python
# Length validation directive
length = SchemaDirective(
    name="length",
    locations=[DirectiveLocation.INPUT_FIELD_DEFINITION],
    args={
        "min": GraphQLArgument(GraphQLInt, description="Minimum length"),
        "max": GraphQLArgument(GraphQLInt, description="Maximum length")
    },
    description="String length validation"
)

# Range validation directive
range_validate = SchemaDirective(
    name="range",
    locations=[DirectiveLocation.INPUT_FIELD_DEFINITION],
    args={
        "min": GraphQLArgument(GraphQLFloat, description="Minimum value"),
        "max": GraphQLArgument(GraphQLFloat, description="Maximum value")
    },
    description="Numeric range validation"
)

# Apply to input types
class CreateUserInput(BaseModel):
    name: str = Field(description="User's full name")
    email: str = Field(description="User's email address")
    age: int = Field(description="User's age")

# With custom field metadata
@api.field(
    directives=[
        AppliedDirective(directive=length, args={"min": 2, "max": 50})
    ]
)
def create_user_with_validation(self, input: CreateUserInput) -> User:
    # Validation can be handled by middleware that reads directives
    return create_user(input)
```

## Using Directives in Middleware

Access directive information in middleware for custom behavior:

```python
def caching_middleware(next_, root, info, **args):
    """Implement caching based on @cache directive."""
    # Check if field has cache directive
    cache_config = None
    for directive in info.field_definition.ast_node.directives:
        if directive.name.value == "cache":
            cache_config = {
                arg.name.value: arg.value.value
                for arg in directive.arguments
            }
            break

    if not cache_config:
        return next_(root, info, **args)

    # Extract cache settings
    ttl = int(cache_config.get("ttl", 60))
    enabled = cache_config.get("enabled", True)

    if not enabled:
        return next_(root, info, **args)

    # Implement caching logic
    cache_key = f"{info.field_name}:{hash(str(args))}"
    cached_result = get_from_cache(cache_key)

    if cached_result is not None:
        return cached_result

    result = next_(root, info, **args)
    set_in_cache(cache_key, result, ttl=ttl)
    return result

def permission_middleware(next_, root, info, **args):
    """Enforce permissions based on @requiresPermission directive."""
    # Check for permission directive
    required_permission = None
    for directive in info.field_definition.ast_node.directives:
        if directive.name.value == "requiresPermission":
            for arg in directive.arguments:
                if arg.name.value == "permission":
                    required_permission = arg.value.value
                    break
            break

    if required_permission:
        user = getattr(info.context, 'current_user', None)
        if not user or not user.has_permission(required_permission):
            raise GraphQLError(f"Permission '{required_permission}' required")

    return next_(root, info, **args)

api = GraphQLAPI(
    directives=[tag, cache, requires_permission],
    middleware=[permission_middleware, caching_middleware]
)
```

## Directive Validation

The library validates directive locations automatically:

```python
# This will raise an error if used incorrectly
object_only_directive = SchemaDirective(
    name="objectOnly",
    locations=[DirectiveLocation.OBJECT]  # Only for objects
)

# ❌ Error: Cannot use @objectOnly on interface
@object_only_directive  # This will fail
@api.type(interface=True)
class InvalidInterface:
    pass

# ✅ Valid: Using on object type
@object_only_directive
@api.type
class ValidObject:
    pass
```

## Best Practices

**Keep directives focused:**
```python
# ✅ Good: Single responsibility
cache = SchemaDirective(
    name="cache",
    locations=[DirectiveLocation.FIELD_DEFINITION],
    args={"ttl": GraphQLArgument(GraphQLString)}
)

# ❌ Avoid: Multiple responsibilities
everything = SchemaDirective(
    name="everything",
    args={
        "cache_ttl": GraphQLArgument(GraphQLString),
        "permission": GraphQLArgument(GraphQLString),
        "rate_limit": GraphQLArgument(GraphQLInt),
        # ... too many concerns
    }
)
```

**Use meaningful names:**
```python
# ✅ Good: Clear, descriptive names
requires_authentication = SchemaDirective(name="requiresAuth", ...)
cache_for_duration = SchemaDirective(name="cache", ...)

# ❌ Avoid: Generic or unclear names
directive1 = SchemaDirective(name="d1", ...)
thing = SchemaDirective(name="thing", ...)
```

**Document directive behavior:**
```python
auth_required = SchemaDirective(
    name="authRequired",
    locations=[DirectiveLocation.FIELD_DEFINITION],
    description="""
    Requires user authentication to access this field.
    Throws an authentication error if no valid user is found in context.
    """,
    args={
        "roles": GraphQLArgument(
            GraphQLList(GraphQLString),
            description="Optional list of required user roles"
        )
    }
)
```

**Make directives composable:**
```python
# Directives should work well together
@requires_permission(permission="read_user")
@cache(ttl="300")
@tag(name="sensitive")
@api.field
def user_data(self) -> str:
    return "User data"
```

Directives provide a powerful way to add declarative metadata and behavior to your GraphQL schema, enabling sophisticated features while keeping your resolvers focused on business logic.