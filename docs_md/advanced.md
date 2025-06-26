# Advanced Topics

This section covers some of the more advanced features of `graphql-api`, including middleware, directives, and Relay support.

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