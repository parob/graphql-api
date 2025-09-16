---
title: "Getting Started"
linkTitle: "Getting Started"
weight: 1
description: >
  This guide will walk you through the process of setting up graphql-api and creating your first GraphQL service.
---

# Getting Started

This guide will walk you through the process of setting up `graphql-api` and creating your first GraphQL service.

## Installation

`graphql-api` requires Python 3.7 or newer. You can install it using `pip`:

```bash
pip install graphql-api
```

## Your First GraphQL API

Let's create a simple GraphQL API that returns a classic "Hello, World!" greeting.

### 1. Initialize the API

First, create a new Python file (e.g., `main.py`) and initialize `GraphQLAPI`:

```python
# main.py
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()
```

### 2. Define the Root Query

Next, define a class that will serve as your root query object. Use the `@api.type` decorator to mark it as the root type for your schema and the `@api.field` decorator to expose a method as a GraphQL field.

```python
# main.py
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type(is_root_type=True)
class Query:
    """
    The root query for our amazing API.
    """
    @api.field
    def hello(self, name: str = "World") -> str:
        """
        Returns a classic greeting. The docstring will be used as the field's description in the schema.
        """
        return f"Hello, {name}!"
```

`graphql-api` uses Python's type hints to generate the GraphQL schema. In this case, `name: str` becomes a required `String` argument, and `-> str` makes the field return a non-null `String`.

### 3. Execute a Query

Now you're ready to execute a query against your API.

```python
# main.py
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type(is_root_type=True)
class Query:
    """
    The root query for our amazing API.
    """
    @api.field
    def hello(self, name: str = "World") -> str:
        """
        Returns a classic greeting. The docstring will be used as the field's description in the schema.
        """
        return f"Hello, {name}!"

# Define a GraphQL query
graphql_query = """
    query Greetings {
        hello(name: "Developer")
    }
"""

# Execute the query
if __name__ == "__main__":
    result = api.execute(graphql_query)
    print(result.data)

```

Run the script from your terminal:

```bash
$ python main.py
{'hello': 'Hello, Developer'}
```

Congratulations! You've successfully created and queried your first GraphQL API with `graphql-api`.

## Exploring Your Schema: Introspection

One of the most powerful features of GraphQL is introspection, which allows you to query the schema itself to understand what queries, types, and fields are available. This is how tools like GraphiQL and Postman can provide autocompletion and documentation on-the-fly.

You can perform an introspection query yourself to see the structure of the schema we just created. For example, to see all the types in your schema:

```python
# main.py
# ... (previous code)

introspection_query = """
    query IntrospectionQuery {
        __schema {
            types {
                name
                kind
            }
        }
    }
"""

if __name__ == "__main__":
    # ... (previous code)
    introspection_result = api.execute(introspection_query)
    # This will print a list of all types in your schema,
    # including standard ones like String, and your custom Query type.
    print(introspection_result.data)

```

Most of the time, you won't write these queries by hand. You'll use a GraphQL client or IDE that has a built-in schema explorer. Simply point the tool to your running API endpoint, and it will use introspection to provide you with a full, interactive guide to your API.

## Next Steps

Now that you've covered the basics, you're ready to explore more advanced features:

- **[Defining Schemas](./defining-schemas.md)**: Learn more about creating complex types, interfaces, and enums.
- **[Pydantic & Dataclasses](./pydantic-and-dataclasses.md)**: Integrate Pydantic models and dataclasses into your schema. 