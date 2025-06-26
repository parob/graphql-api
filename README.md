# GraphQL API for Python

A powerful and intuitive Python library for building GraphQL APIs, designed with a code-first, decorator-based approach.

[![coverage report](https://gitlab.com/parob/graphql-api/badges/master/coverage.svg)](https://gitlab.com/parob/graphql-api/commits/master)

[![pipeline status](https://gitlab.com/parob/graphql-api/badges/master/pipeline.svg)](https://gitlab.com/parob/graphql-api/commits/master)

`graphql-api` simplifies schema definition by leveraging Python's type hints, dataclasses, and Pydantic models, allowing you to build robust and maintainable GraphQL services with minimal boilerplate.

## Key Features

- **Decorator-Based Schema:** Define your GraphQL schema declaratively using simple and intuitive decorators.
- **Type Hinting:** Automatically converts Python type hints into GraphQL types.
- **Pydantic & Dataclass Support:** Seamlessly use Pydantic and Dataclass models as GraphQL types.
- **Asynchronous Execution:** Full support for `async` and `await` for high-performance, non-blocking resolvers.
- **Apollo Federation:** Built-in support for creating federated services.
- **Subscriptions:** Implement real-time functionality with GraphQL subscriptions.
- **Middleware:** Add custom logic to your resolvers with a flexible middleware system.
- **Relay Support:** Includes helpers for building Relay-compliant schemas.

## Installation

```bash
pip install graphql-api
```

## Quick Start

Create a simple GraphQL API in just a few lines of code.

```python
# example.py
from graphql_api.api import GraphQLAPI

# 1. Initialize the API
api = GraphQLAPI()

# 2. Define your root type with decorators
@api.type(is_root_type=True)
class Query:
    """
    The root query for our amazing API.
    """
    @api.field
    def hello(self, name: str = "World") -> str:
        """
        A classic greeting.
        """
        return f"Hello, {name}!"

# 3. Define a query
graphql_query = """
    query Greetings {
        hello(name: "Developer")
    }
"""

# 4. Execute the query
if __name__ == "__main__":
    result = api.execute(graphql_query)
    print(result.data)
```

Running this script will produce:

```bash
$ python example.py
{'hello': 'Hello, Developer'}
```

## Examples

### Using Pydantic Models

Leverage Pydantic for data validation and structure. `graphql-api` will automatically convert your models into GraphQL types.

```python
from pydantic import BaseModel
from typing import List
from graphql_api.api import GraphQLAPI

class Book(BaseModel):
    title: str
    author: str

class BookAPI:
    @api.field
    def get_books(self) -> List[Book]:
        return [
            Book(title="The Hitchhiker's Guide to the Galaxy", author="Douglas Adams"),
            Book(title="1984", author="George Orwell"),
        ]

api = GraphQLAPI(root_type=BookAPI)

graphql_query = """
    query {
        getBooks {
            title
            author
        }
    }
"""

result = api.execute(graphql_query)
# result.data will contain the list of books
```

### Asynchronous Resolvers

Define async resolvers for non-blocking I/O operations.

```python
import asyncio
from graphql_api.api import GraphQLAPI

class AsyncAPI:
    @api.field
    async def fetch_data(self) -> str:
        await asyncio.sleep(1)
        return "Data fetched successfully!"

api = GraphQLAPI(root_type=AsyncAPI)

# To execute async queries, you'll need an async executor
# or to run it within an async context.
async def main():
    result = await api.execute_async("""
        query {
            fetchData
        }
    """)
    print(result.data)

if __name__ == "__main__":
    asyncio.run(main())

```
*Note: `execute_async` is a conceptual example. Refer to `test_async.py` for concrete implementation details.*


### Mutations with Dataclasses

Use dataclasses to define the structure of your mutation inputs.

```python
from dataclasses import dataclass
from graphql_api.api import GraphQLAPI, field

@dataclass
class User:
    id: int
    name: str

# A simple in-memory database
db = {1: User(id=1, name="Alice")}

class Root:
    @field
    def get_user(self, user_id: int) -> User:
        return db.get(user_id)

class Mutations:
    @field
    def add_user(self, user_id: int, name: str) -> User:
        new_user = User(id=user_id, name=name)
        db[user_id] = new_user
        return new_user

# The GraphQLAPI constructor will need to be updated to support mutations separately
# api = GraphQLAPI(root_type=Root, mutation_type=Mutations)
```
*Note: The mutation API is illustrative. The library's `GraphQLAPI` constructor may need to be extended to support mutations as shown.*

## Running Tests

To contribute or run the test suite locally:

```bash
# Install dependencies
pip install pipenv
pipenv install --dev

# Run tests
pipenv run pytest
```

## Documentation

For more in-depth information, you can build the documentation locally.

```bash
pipenv run sphinx-build docs ./public -b html
```
Then open `public/index.html` in your browser. Note that some documentation may be outdated. For the latest features, please refer to the tests.
