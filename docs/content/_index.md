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

- 📚 **[Getting Started](docs/getting-started/)** - Learn the basics with our comprehensive guide
- 💡 **[Examples](docs/examples/)** - Explore practical examples and tutorials for real-world scenarios  
- 📖 **[API Reference](docs/api-reference/)** - Check out the complete API documentation