# Asynchronous Resolvers and Subscriptions

`graphql-api` fully supports modern asynchronous Python, allowing you to build high-performance, non-blocking GraphQL services.

## Asynchronous Resolvers

You can define `async` resolvers for fields that perform I/O-bound operations, such as database queries or calls to external APIs. `graphql-api` will handle the execution of these resolvers within an async context.

### Defining an Async Field

To create an asynchronous resolver, simply define a resolver method using `async def`.

```python
import asyncio
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type(is_root_type=True)
class Query:
    @api.field
    async def fetch_remote_data(self) -> str:
        """
        Simulates fetching data from a remote service.
        """
        # In a real application, this could be an HTTP request
        # or a database query using an async library.
        await asyncio.sleep(1)
        return "Data fetched successfully!"
```

### Executing Async Queries

To execute a schema with async resolvers, you'll need to use an async-native web framework like Starlette or FastAPI. The `graphql-api` library can be easily integrated.

The following is a conceptual example of how you might integrate with Starlette. For a complete, runnable example, please refer to the `test_async.py` and `test_subscriptions.py` files in the test suite.

```python
# Conceptual integration with an ASGI framework like Starlette
# from starlette.applications import Starlette
# from starlette.responses import JSONResponse
# from starlette.routing import Route

# async def graphql_endpoint(request):
#     data = await request.json()
#     result = await api.execute_async(query=data['query'])
#     return JSONResponse(result)

# routes = [
#     Route("/graphql", endpoint=graphql_endpoint, methods=["POST"]),
# ]

# app = Starlette(routes=routes)
```

## Subscriptions

`graphql-api` supports GraphQL subscriptions to enable real-time communication with clients. Subscriptions are defined as `async` generators that `yield` data to the client over time.

### Defining a Subscription

A common pattern is to define a `Subscription` class and pass it to the `GraphQLAPI` constructor. The resolver for a subscription field must be an `async` generator.

```python
import asyncio
from typing import AsyncGenerator
from graphql_api.api import GraphQLAPI

class Subscription:
    @api.field
    async def count(self, to: int = 5) -> AsyncGenerator[int, None]:
        """
        Counts up to a given number, yielding each number.
        """
        for i in range(1, to + 1):
            await asyncio.sleep(1)  # Simulate a real-time event
            yield i

# To enable subscriptions, you would pass the Subscription class
# to the API constructor. This requires modifications to the
# GraphQLAPI class to accept a `subscription_type`.
# api = GraphQLAPI(root_type=Query, subscription_type=Subscription)
```

This would generate a `Subscription` type in your schema:

```graphql
type Subscription {
  count(to: Int = 5): Int!
}
```

When a client initiates a subscription operation, they will open a persistent connection (e.g., a WebSocket) and receive a new value each time the `yield` statement is executed in the resolver. This powerful feature allows you to build engaging, real-time experiences for your users. 