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

`graphql-api` offers two approaches for defining subscriptions:

### Mode 1: Single Root Type (Recommended)

In this mode, you define all operations (queries, mutations, subscriptions) in a single root class. Subscription fields are automatically detected by their `AsyncGenerator` return type:

```python
import asyncio
from typing import AsyncGenerator
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type(is_root_type=True)
class Root:
    # Query field
    @api.field
    def get_user(self, user_id: int) -> User:
        return get_user_from_db(user_id)
    
    # Mutation field
    @api.field(mutable=True)
    def update_user(self, user_id: int, name: str) -> User:
        return update_user_in_db(user_id, name)
    
    # Subscription field - automatically detected by AsyncGenerator return type
    @api.field
    async def on_user_updated(self, user_id: int) -> AsyncGenerator[User, None]:
        """Real-time user updates"""
        while True:
            # In a real app, this would listen to a message queue or database changes
            await asyncio.sleep(1)
            yield get_user_from_db(user_id)
    
    # You can also explicitly mark fields as subscriptions
    @api.field(subscription=True) 
    async def count(self, to: int = 5) -> AsyncGenerator[int, None]:
        """Counts up to a given number, yielding each number."""
        for i in range(1, to + 1):
            await asyncio.sleep(1)
            yield i

api_with_root = GraphQLAPI(root_type=Root)
```

### Mode 2: Explicit Types

For more complex applications, you can define separate classes for queries, mutations, and subscriptions:

```python
import asyncio
from typing import AsyncGenerator
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type
class Query:
    @api.field
    def get_user(self, user_id: int) -> User:
        return get_user_from_db(user_id)

@api.type
class Mutation:
    @api.field
    def update_user(self, user_id: int, name: str) -> User:
        return update_user_in_db(user_id, name)

@api.type
class Subscription:
    @api.field
    async def on_user_updated(self, user_id: int) -> AsyncGenerator[User, None]:
        """Real-time user updates"""
        while True:
            await asyncio.sleep(1)
            yield get_user_from_db(user_id)

# Use explicit types mode
api_explicit = GraphQLAPI(
    query_type=Query,
    mutation_type=Mutation,
    subscription_type=Subscription
)
```

This would generate a `Subscription` type in your schema:

```graphql
type Subscription {
  count(to: Int = 5): Int!
}
```

When a client initiates a subscription operation, they will open a persistent connection (e.g., a WebSocket) and receive a new value each time the `yield` statement is executed in the resolver. This powerful feature allows you to build engaging, real-time experiences for your users. 