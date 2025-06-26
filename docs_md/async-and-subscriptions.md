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
        await asyncio.sleep(1)  # Simulate a network request
        return "Data fetched successfully!"
```

### Executing Async Queries

When your schema contains asynchronous resolvers, you'll need to use an async-compatible method to execute your queries. The exact method may vary depending on the web framework you are using, but the principle remains the same.

The following is a conceptual example of how you might execute an async query. For a concrete implementation, please refer to the `test_async.py` file in the test suite.

```python
import asyncio

# Conceptual async execution
async def main():
    graphql_query = """
        query {
            fetchRemoteData
        }
    """
    # In a real-world scenario, you would use an async-capable
    # executor or integration (e.g., with Starlette or FastAPI).
    # result = await api.execute_async(graphql_query)
    # print(result.data)

if __name__ == "__main__":
    # To run the conceptual example:
    # asyncio.run(main())
    pass
```

## Subscriptions

`graphql-api` supports GraphQL subscriptions, enabling real-time communication with clients. Subscriptions are useful for features like live notifications, chat applications, and real-time data updates.

### Defining a Subscription

Subscriptions are defined similarly to queries, but they typically involve an `async` generator (`async yield`) to push updates to the client.

```python
import asyncio
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type(is_root_type=True)
class Query:
    # Your regular queries go here
    pass

class Subscription:
    @api.field
    async def count(self, to: int = 5):
        """
        Counts up to a given number, yielding each number.
        """
        for i in range(to):
            await asyncio.sleep(1)
            yield i

# The GraphQLAPI constructor would need to be updated to support subscriptions.
# api = GraphQLAPI(root_type=Query, subscription_type=Subscription)
```

This would generate a `Subscription` type in your schema:

```graphql
type Subscription {
  count(to: Int!): Int!
}
```

When a client subscribes to the `count` field, it will receive a new number every second until the count is complete. This powerful feature allows you to build engaging, real-time experiences for your users. 