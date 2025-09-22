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

A middleware is a function that takes the next resolver in the chain and the same arguments as a regular resolver (`obj`, `info`, etc.).

```python
def timing_middleware(next, obj, info, **kwargs):
    """
    A simple middleware to measure resolver execution time.
    """
    import time
    start_time = time.time()
    result = next(obj, info, **kwargs)
    end_time = time.time()
    print(f"Resolver {info.field_name} took {end_time - start_time:.2f}s")
    return result
```

### Applying Middleware

You can apply middleware globally when you initialize your API:

```python
from graphql_api.api import GraphQLAPI

api = GraphQLAPI(middleware=[timing_middleware])
```

When a query is executed, the `timing_middleware` will be called for each resolved field, providing valuable performance insights.

## Error Handling

Proper error handling is crucial for a robust API. `graphql-api` allows you to customize how errors are handled and reported to the client.

### Custom Exceptions

You can define custom exception classes that will be automatically formatted into GraphQL errors. This is useful for representing specific error scenarios, like "not found" or "permission denied."

```python
from graphql_api.error import GraphQLError

class UserNotFoundError(GraphQLError):
    """A specific error for when a user is not found."""
    def __init__(self, user_id: int):
        super().__init__(
            f"User with ID {user_id} not found.",
            extensions={"code": "USER_NOT_FOUND"}
        )

# In a resolver, you can raise this exception
@api.type(is_root_type=True)
class Query:
    @api.field
    def get_user_by_id(self, user_id: int) -> User:
        user = find_user_in_db(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user
```

When this resolver is executed with an invalid ID, the client will receive a structured error in the response:

```json
{
  "errors": [
    {
      "message": "User with ID 123 not found.",
      "locations": [...],
      "path": ["getUserById"],
      "extensions": {
        "code": "USER_NOT_FOUND"
      }
    }
  ],
  "data": {
    "getUserById": null
  }
}
```

This allows clients to handle specific error cases programmatically.

## Resolver Context

Sometimes, your resolvers need access to request-specific information, such as the current user's authentication details, HTTP headers, or a database connection. `graphql-api` provides a `context` object for this purpose.

The context is a dictionary that is passed to every resolver during the execution of a query. You can populate it when you execute the query.

### Populating the Context

```python
# When executing a query, you can pass a `context` dictionary.
result = api.execute(
    query,
    context={
        "current_user": get_user_from_request(request),
        "db_session": create_db_session()
    }
)
```

### Accessing the Context in Resolvers

The context is available via the `info` argument (which is of type `GraphQLResolveInfo`) that is passed to every resolver.

```python
@api.type(is_root_type=True)
class Query:
    @api.field
    def get_my_profile(self, info) -> User:
        # Access the context from the `info` object.
        current_user = info.context.get("current_user")

        if not current_user:
            raise PermissionError("You must be logged in to view your profile.")

        return current_user
```

Using the context is the recommended way to provide resolvers with request-scoped data, keeping them decoupled from the transport layer (e.g., HTTP).

## Directives

`graphql-api` supports custom directives, which allow you to add declarative, reusable logic to your schema.

### Defining a Directive

To define a directive, use the `@api.directive` decorator. You can also specify the locations where the directive can be used (e.g., `FIELD`, `ARGUMENT_DEFINITION`).

```python
from graphql_api.api import GraphQLAPI
from graphql import DirectiveLocation

api = GraphQLAPI()

@api.directive(locations=[DirectiveLocation.FIELD])
def uppercase(value):
    """
    A directive to transform a string field to uppercase.
    """
    return value.upper()
```

### Using a Directive

Once defined, you can apply the directive in your schema definition using the `directives` parameter on a field.

```python
@api.type(is_root_type=True)
class Query:
    @api.field(directives=[uppercase])
    def get_greeting(self) -> str:
        return "hello, world!"
```

When you query the `getGreeting` field, the `uppercase` directive will be applied, and the result will be `"HELLO, WORLD!"`.

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