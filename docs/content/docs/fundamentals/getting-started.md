---
title: "Getting Started"
weight: 1
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

`graphql-api` uses Python's type hints to generate the GraphQL schema. In this case, `name: str = "World"` becomes an optional `String` argument (nullable because it has a default value), and `-> str` makes the field return a non-null `String`.

#### Understanding Type Nullability

In GraphQL and `graphql-api`:
- **Arguments with default values** become nullable (optional) in GraphQL
- **Arguments without defaults** become non-null (required) in GraphQL
- **Return types** are non-null by default unless wrapped in `Optional[T]`

For example:
```python
@api.field
def example(self, required_arg: str, optional_arg: str = "default") -> str:
    return f"{required_arg} {optional_arg}"
```

This generates:
```graphql
example(requiredArg: String!, optionalArg: String): String!
```

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

## Error Handling

GraphQL APIs can return both data and errors. Here's how to handle potential errors in your queries:

```python
result = api.execute(graphql_query)

if result.errors:
    print("GraphQL errors occurred:")
    for error in result.errors:
        print(f"- {error.message}")
else:
    print("Success:", result.data)
```

Common types of errors include:
- **Syntax errors**: Invalid GraphQL query syntax
- **Validation errors**: Query doesn't match the schema (e.g., requesting non-existent fields)
- **Execution errors**: Errors thrown by your resolver functions

```python
@api.type(is_root_type=True)
class Query:
    @api.field
    def divide(self, a: int, b: int) -> float:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

# This will return an execution error
result = api.execute('query { divide(a: 10, b: 0) }')
# result.errors will contain the ValueError
```

## Schema Documentation with Docstrings

`graphql-api` automatically converts Python docstrings into GraphQL schema descriptions, making your API self-documenting:

```python
@api.type(is_root_type=True)
class Query:
    """
    The root query type for our API.
    This docstring becomes the type description.
    """

    @api.field
    def get_user(self, user_id: str) -> str:
        """
        Retrieve a user by their unique ID.

        This docstring becomes the field description in the GraphQL schema.
        """
        return f"User {user_id}"

    @api.field
    def search_users(self, query: str, limit: int = 10) -> List[str]:
        """Search for users matching a query string."""
        return [f"User matching '{query}'"]
```

### Dataclass and Pydantic Documentation

Docstrings work with all type definitions:

```python
from dataclasses import dataclass
from pydantic import BaseModel

@dataclass
class User:
    """Represents a user in the system."""
    id: str
    """The unique identifier for the user."""
    name: str
    """The user's display name."""
    email: str

class CreateUserInput(BaseModel):
    """Input data for creating a new user."""
    name: str
    email: str
```

### Advanced Docstring Parsing

The library supports Google-style docstrings for more structured documentation:

```python
@dataclass
class Product:
    """
    A product in our catalog.

    Args:
        id: The unique product identifier
        name: The product display name
        price: The product price in cents
        category: The product category name
    """
    id: str
    name: str
    price: int
    category: str
```

**Automatic Features:**
- Class docstrings become GraphQL type descriptions
- Method docstrings become field descriptions
- Dataclass field docstrings are extracted
- Google-style Args sections are parsed for field descriptions
- Pydantic model docstrings are preserved
- Default Pydantic docstrings are filtered out

This documentation appears in GraphQL introspection and tools like GraphiQL, making your API easy to explore and understand.

## What's Next

Now that you have a working GraphQL API, you can explore more features:

**Building schemas:** [Schema Definition](defining-schemas/) covers decorator patterns and schema definition in detail.

**Working with types:**
- [Field Types](field-types/) - All supported scalar and collection types
- [Object Types & Relationships](object-types/) - Complex interconnected types
- [Documentation](documentation/) - Add rich documentation to your schemas

**Building applications:** When you're ready to create full applications, explore [Input Types & Mutations](mutations/) for data modifications.