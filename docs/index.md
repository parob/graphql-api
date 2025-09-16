---
layout: default
title: "GraphQL API for Python"
description: "A powerful and intuitive Python library for building GraphQL APIs with a code-first, decorator-based approach."
---

# GraphQL API for Python

A powerful and intuitive Python library for building GraphQL APIs, designed with a code-first, decorator-based approach.

[![PyPI version](https://badge.fury.io/py/graphql-api.svg)](https://badge.fury.io/py/graphql-api)
[![Python versions](https://img.shields.io/pypi/pyversions/graphql-api.svg)](https://pypi.org/project/graphql-api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Why GraphQL API?

`graphql-api` simplifies schema definition by leveraging Python's type hints, dataclasses, and Pydantic models, allowing you to build robust and maintainable GraphQL services with minimal boilerplate.

<div class="feature-grid">
  <div class="feature">
    <h3>🎯 Code-First Approach</h3>
    <p>Define your GraphQL schema using Python decorators and type hints. No SDL required.</p>
  </div>
  <div class="feature">
    <h3>⚡ Type Safety</h3>
    <p>Automatic type conversion from Python types to GraphQL types with full type checking support.</p>
  </div>
  <div class="feature">
    <h3>🔄 Async Support</h3>
    <p>Built-in support for async/await patterns and real-time subscriptions.</p>
  </div>
  <div class="feature">
    <h3>🧩 Pydantic Integration</h3>
    <p>Seamlessly use Pydantic models and dataclasses as GraphQL types.</p>
  </div>
  <div class="feature">
    <h3>🌐 Federation Ready</h3>
    <p>Built-in Apollo Federation support for microservice architectures.</p>
  </div>
  <div class="feature">
    <h3>🎛️ Flexible Schema</h3>
    <p>Choose between unified root types or explicit query/mutation/subscription separation.</p>
  </div>
</div>

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

## Documentation

<div class="docs-grid">
  <div class="doc-card">
    <h3><a href="./getting-started.html">📚 Getting Started</a></h3>
    <p>A comprehensive guide for new users, from installation to your first query.</p>
  </div>
  <div class="doc-card">
    <h3><a href="./defining-schemas.html">🏗️ Defining Schemas</a></h3>
    <p>Learn how to define your GraphQL schema, types, and fields using decorators.</p>
  </div>
  <div class="doc-card">
    <h3><a href="./pydantic-and-dataclasses.html">🧩 Pydantic & Dataclasses</a></h3>
    <p>Seamlessly integrate Pydantic models and dataclasses into your schema.</p>
  </div>
  <div class="doc-card">
    <h3><a href="./async-and-subscriptions.html">⚡ Async & Subscriptions</a></h3>
    <p>Implement high-performance, non-blocking resolvers and real-time functionality.</p>
  </div>
  <div class="doc-card">
    <h3><a href="./federation.html">🌐 Apollo Federation</a></h3>
    <p>Build and manage distributed graphs with built-in support for Apollo Federation.</p>
  </div>
  <div class="doc-card">
    <h3><a href="./advanced.html">🚀 Advanced Topics</a></h3>
    <p>Explore advanced features like custom middleware, directives, and Relay support.</p>
  </div>
</div>

## Get Started Now

<div class="cta-section">
  <a href="./getting-started.html" class="btn btn-primary">Get Started</a>
  <a href="https://github.com/parob/graphql-api" class="btn btn-secondary">View on GitHub</a>
</div>

---

<style>
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.feature {
  padding: 1.5rem;
  border: 1px solid #e1e4e8;
  border-radius: 6px;
  background: #f8f9fa;
}

.feature h3 {
  margin-top: 0;
  color: #0366d6;
}

.docs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin: 2rem 0;
}

.doc-card {
  padding: 1rem;
  border: 1px solid #e1e4e8;
  border-radius: 6px;
  background: white;
  transition: box-shadow 0.2s;
}

.doc-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.doc-card h3 {
  margin-top: 0;
  margin-bottom: 0.5rem;
}

.doc-card h3 a {
  color: #0366d6;
  text-decoration: none;
}

.doc-card h3 a:hover {
  text-decoration: underline;
}

.cta-section {
  text-align: center;
  margin: 3rem 0;
}

.btn {
  display: inline-block;
  padding: 0.75rem 1.5rem;
  margin: 0 0.5rem;
  text-decoration: none;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-primary {
  background-color: #0366d6;
  color: white;
}

.btn-primary:hover {
  background-color: #0256cc;
  text-decoration: none;
  color: white;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #586069;
  border: 1px solid #d1d5da;
}

.btn-secondary:hover {
  background-color: #e1e4e8;
  text-decoration: none;
  color: #586069;
}
</style> 