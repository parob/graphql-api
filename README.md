# GraphQL-API for Python

[![PyPI version](https://badge.fury.io/py/graphql-api.svg)](https://badge.fury.io/py/graphql-api)
[![Python versions](https://img.shields.io/pypi/pyversions/graphql-api.svg)](https://pypi.org/project/graphql-api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage](https://gitlab.com/parob/graphql-api/badges/master/coverage.svg)](https://gitlab.com/parob/graphql-api/commits/master)
[![Pipeline](https://gitlab.com/parob/graphql-api/badges/master/pipeline.svg)](https://gitlab.com/parob/graphql-api/commits/master)

**[📚 Documentation](https://graphql-api.parob.com/)** | **[📦 PyPI](https://pypi.org/project/graphql-api/)** | **[🔧 GitHub](https://github.com/parob/graphql-api)**

---

A powerful and intuitive Python library for building GraphQL APIs, designed with a code-first, decorator-based approach.

`graphql-api` simplifies schema definition by leveraging Python's type hints, dataclasses, and Pydantic models, allowing you to build robust and maintainable GraphQL services with minimal boilerplate.

## Key Features

- **Decorator-Based Schema:** Define your GraphQL schema declaratively using simple and intuitive decorators.
- **Type Hinting:** Automatically converts Python type hints into GraphQL types.
- **Implicit Type Inference:** Automatically maps Pydantic models, dataclasses, and classes with fields - no explicit decorators needed.
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

@api.type(is_root_type=True)
class BookAPI:
    @api.field
    def get_books(self) -> List[Book]:
        return [
            Book(title="The Hitchhiker's Guide to the Galaxy", author="Douglas Adams"),
            Book(title="1984", author="George Orwell"),
        ]

api = GraphQLAPI()

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

api = GraphQLAPI()

@api.type(is_root_type=True)
class AsyncAPI:
    @api.field
    async def fetch_data(self) -> str:
        await asyncio.sleep(1)
        return "Data fetched successfully!"

# To execute async queries, you'll need an async executor
# or to run it within an async context.
async def main():
    result = await api.execute("""
        query {
            fetchData
        }
    """)
    print(result.data)

if __name__ == "__main__":
    asyncio.run(main())

```


### Mutations with Dataclasses

Use dataclasses to define the structure of your data, and mark fields as mutable to automatically separate them into the GraphQL Mutation type.

```python
from dataclasses import dataclass
from graphql_api.api import GraphQLAPI

@dataclass
class User:
    id: int
    name: str

# A simple in-memory database
db = {1: User(id=1, name="Alice")}

api = GraphQLAPI()

@api.type(is_root_type=True)
class Root:
    @api.field
    def get_user(self, user_id: int) -> User:
        return db.get(user_id)

    @api.field(mutable=True)
    def add_user(self, user_id: int, name: str) -> User:
        new_user = User(id=user_id, name=name)
        db[user_id] = new_user
        return new_user
```

GraphQL automatically separates queries and mutations - you don't need separate classes. Fields marked with `mutable=True` are placed in the Mutation type, while regular fields go in the Query type. Fields with `AsyncGenerator` return types are automatically detected as subscriptions. This automatic mapping means you can define all your operations in a single class and let `graphql-api` handle the schema organization for you.

## Related Projects

- **[graphql-http](https://graphql-http.parob.com/)** - Serve your API over HTTP with authentication and GraphiQL
- **[graphql-db](https://graphql-db.parob.com/)** - SQLAlchemy integration for database-backed APIs
- **[graphql-mcp](https://graphql-mcp.parob.com/)** - Expose your API as MCP tools for AI agents

See the [documentation](https://graphql-api.parob.com/) for advanced schema patterns, federation, remote GraphQL, and more.

## Documentation

**Visit the [official documentation](https://graphql-api.parob.com/)** for comprehensive guides, tutorials, and API reference.

### Key Topics

- **[Getting Started](https://graphql-api.parob.com/docs/fundamentals/getting-started/)** - Quick introduction and basic usage
- **[Defining Schemas](https://graphql-api.parob.com/docs/fundamentals/defining-schemas/)** - Learn schema definition patterns
- **[Field Types](https://graphql-api.parob.com/docs/fundamentals/field-types/)** - Understanding GraphQL type system
- **[Mutations](https://graphql-api.parob.com/docs/fundamentals/mutations/)** - Implementing data modifications
- **[Remote GraphQL](https://graphql-api.parob.com/docs/distributed-systems/remote-graphql/)** - Connect to remote APIs
- **[Federation](https://graphql-api.parob.com/docs/distributed-systems/federation/)** - Apollo Federation support
- **[API Reference](https://graphql-api.parob.com/docs/reference/api-reference/)** - Complete API documentation

## Running Tests

To contribute or run the test suite locally:

```bash
# Install dependencies
pip install pipenv
pipenv install --dev

# Run tests
pipenv run pytest
```