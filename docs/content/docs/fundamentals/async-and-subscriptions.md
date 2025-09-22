---
title: "Async & Subscriptions"
weight: 9
description: >
  Build high-performance async resolvers and real-time subscriptions
---

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

**Important**: `graphql-api` automatically handles async resolvers! You can use the standard `api.execute()` method even with async resolvers - no special async execution is required.

```python
# This works with async resolvers!
result = api.execute("query { fetchRemoteData }")
```

The library internally manages the async execution, so you don't need to worry about `await` or event loops when using async resolvers.

#### Integration with Web Frameworks

For web applications, you can integrate with both sync and async frameworks:

**With FastAPI (async framework):**
```python
from fastapi import FastAPI
from graphql_api.api import GraphQLAPI

app = FastAPI()
api = GraphQLAPI()

@api.type(is_root_type=True)
class Query:
    @api.field
    async def fetch_data(self) -> str:
        # Your async logic here
        return "data"

@app.post("/graphql")
async def graphql_endpoint(query: str):
    result = api.execute(query)  # Works seamlessly!
    return result.data
```

**With Flask (sync framework):**
```python
from flask import Flask
from graphql_api.api import GraphQLAPI

app = Flask(__name__)
api = GraphQLAPI()

@api.type(is_root_type=True)
class Query:
    @api.field
    async def fetch_data(self) -> str:
        # Your async logic here
        return "data"

@app.route("/graphql", methods=["POST"])
def graphql_endpoint():
    result = api.execute(request.json["query"])  # Also works!
    return result.data
```

## Subscriptions

`graphql-api` supports GraphQL subscriptions to enable real-time communication with clients. Subscriptions are defined as `async` generators that `yield` data to the client over time.

Subscriptions can be defined using either of the two schema definition modes described in the [Defining Schemas](../defining-schemas/#schema-definition-modes) documentation:

### Subscription Examples

**Using Mode 1 (Single Root Type):**

```python
import asyncio
from typing import AsyncGenerator
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type(is_root_type=True)
class Root:
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
```

**Using Mode 2 (Explicit Types):**

```python
import asyncio
from typing import AsyncGenerator
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type
class Subscription:
    @api.field
    async def on_user_updated(self, user_id: int) -> AsyncGenerator[User, None]:
        """Real-time user updates"""
        while True:
            await asyncio.sleep(1)
            yield get_user_from_db(user_id)

    @api.field
    async def count(self, to: int = 5) -> AsyncGenerator[int, None]:
        """Counts up to a given number, yielding each number."""
        for i in range(1, to + 1):
            await asyncio.sleep(1)
            yield i

# Use explicit types mode
api_explicit = GraphQLAPI(subscription_type=Subscription)
```

This would generate a `Subscription` type in your schema:

```graphql
type Subscription {
  count(to: Int = 5): Int!
}
```

When a client initiates a subscription operation, they will open a persistent connection (e.g., a WebSocket) and receive a new value each time the `yield` statement is executed in the resolver. This powerful feature allows you to build engaging, real-time experiences for your users.