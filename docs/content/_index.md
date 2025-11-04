---
title: "GraphQL API for Python"
type: docs
---

> **A powerful and intuitive Python library for building GraphQL APIs with a code-first, decorator-based approach.**

# GraphQL API for Python

[![PyPI version](https://badge.fury.io/py/graphql-api.svg)](https://badge.fury.io/py/graphql-api)
[![Python versions](https://img.shields.io/pypi/pyversions/graphql-api.svg)](https://pypi.org/project/graphql-api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Why GraphQL API?

`graphql-api` simplifies schema definition by leveraging Python's type hints, dataclasses, and Pydantic models, allowing you to build robust and maintainable GraphQL services with minimal boilerplate.

## Key Features

| Feature | Description |
|---------|-------------|
| 🎯 **Code-First Approach** | Define your GraphQL schema using Python decorators and type hints. No SDL required. |
| ⚡ **Type Safety** | Automatic type conversion from Python types to GraphQL types with full type checking support. |
| 🔄 **Async Support** | Built-in support for async/await patterns and real-time subscriptions. |
| 🧩 **Pydantic Integration** | Seamlessly use Pydantic models and dataclasses as GraphQL types. |
| 🌐 **Federation Ready** | Built-in Apollo Federation support for microservice architectures. |
| 🎛️ **Flexible Schema** | Choose between unified root types or explicit query/mutation/subscription separation. |

## Quick Start

Get up and running in minutes:

```bash
pip install graphql-api
```

```python
from graphql_api.api import GraphQLAPI

# Initialize the API
api = GraphQLAPI()

# Define your schema with decorators
@api.type(is_root_type=True)
class Query:
    @api.field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

# Execute queries
result = api.execute('{ hello(name: "Developer") }')
print(result.data)  # {'hello': 'Hello, Developer!'}
```

## Related Projects

`graphql-api` focuses on schema definition and execution. For additional functionality:

### HTTP Server: graphql-http

Serve your GraphQL API over HTTP with [graphql-http](https://graphql-http.parob.com/):

- 🚀 High-performance ASGI server built on Starlette
- 🔐 JWT authentication with JWKS support
- 🎨 Integrated GraphiQL interface
- 🌐 CORS support and health checks

```python
from graphql_api import GraphQLAPI
from graphql_http import GraphQLHTTP

api = GraphQLAPI()
# ... define your schema ...

server = GraphQLHTTP.from_api(api)
server.run()
```

**Learn more**: [graphql-http documentation](https://graphql-http.parob.com/)

### Database Integration: graphql-db

Build database-backed APIs with SQLAlchemy using [graphql-db](https://graphql-db.parob.com/):

```python
from graphql_api import GraphQLAPI
from graphql_db.orm_base import DatabaseManager, ModelBase

# Define models and create API
api = GraphQLAPI()
# ... graphql-db handles database integration ...
```

**Learn more**: [graphql-db documentation](https://graphql-db.parob.com/)

### MCP Tools: graphql-mcp

Expose your GraphQL API as MCP tools for AI agents with [graphql-mcp](https://graphql-mcp.parob.com/):

```python
from graphql_api import GraphQLAPI
from graphql_mcp.server import GraphQLMCP

api = GraphQLAPI()
# ... define your schema ...

server = GraphQLMCP.from_api(api)
app = server.http_app()
```

**Learn more**: [graphql-mcp documentation](https://graphql-mcp.parob.com/)

## Key Features

- **Decorator-Based Schema:** Define your GraphQL schema declaratively using simple and intuitive decorators
- **Type Hinting:** Automatically converts Python type hints into GraphQL types
- **Implicit Type Inference:** Automatically maps Pydantic models, dataclasses, and classes with fields
- **Pydantic & Dataclass Support:** Seamlessly use Pydantic and Dataclass models as GraphQL types
- **Asynchronous Execution:** Full support for `async` and `await` for high-performance, non-blocking resolvers
- **Apollo Federation:** Built-in support for creating federated services
- **Subscriptions:** Implement real-time functionality with GraphQL subscriptions
- **Middleware:** Add custom logic to your resolvers with a flexible middleware system
- **Relay Support:** Includes helpers for building Relay-compliant schemas

## What's Next?

- 📚 **[Getting Started](docs/fundamentals/getting-started/)** - Learn the basics with our comprehensive guide
- 💡 **[Examples](docs/reference/examples/)** - Explore practical examples and tutorials for real-world scenarios
- 📖 **[API Reference](docs/reference/api-reference/)** - Check out the complete API documentation