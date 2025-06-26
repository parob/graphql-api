# Defining Schemas

`graphql-api` uses a decorator-based, code-first approach to schema definition. This allows you to define your entire GraphQL schema using Python classes, methods, and type hints.

## Core Concepts

- **`@api.type`**: A class decorator that marks a Python class as a GraphQL object type.
- **`@api.field`**: A method decorator that exposes a class method as a field on a GraphQL type.
- **Type Hinting**: Python type hints are used to determine the GraphQL types for fields, arguments, and return values.

## Defining Object Types

To define a GraphQL object type, simply decorate a Python class with `@api.type`.

```python
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type
class User:
    """Represents a user in the system."""
    @api.field
    def id(self) -> int:
        return 1

    @api.field
    def name(self) -> str:
        return "Alice"

# In your root query, you can now return this type
@api.type(is_root_type=True)
class Query:
    @api.field
    def get_user(self) -> User:
        return User()
```

This will generate the following GraphQL schema:

```graphql
type User {
  id: Int!
  name: String!
}

type Query {
  getUser: User!
}
```

## Fields and Resolvers

Each method decorated with `@api.field` within a GraphQL type class becomes a field in the schema. The method itself acts as the resolver for that field.

### Field Arguments

To add arguments to a field, simply add them as parameters to the resolver method, complete with type hints.

```python
@api.type(is_root_type=True)
class Query:
    @api.field
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
```

This maps to:

```graphql
type Query {
  greet(name: String!): String!
}
```

### Type Modifiers

GraphQL's type modifiers (List and Non-Null) are handled automatically based on your Python type hints.

- **Non-Null**: By default, all fields and arguments are non-nullable. To make a type nullable, use `Optional` from the `typing` module.
- **List**: To define a list of a certain type, use `List` from the `typing` module.

```python
from typing import List, Optional

@api.type
class Post:
    @api.field
    def id(self) -> int:
        return 123

    @api.field
    def title(self) -> str:
        return "My First Post"

    @api.field
    def summary(self) -> Optional[str]:
        return None # This field can be null

@api.type(is_root_type=True)
class Query:
    @api.field
    def get_posts(self) -> List[Post]:
        return [Post()]
```

This generates the following schema:

```graphql
type Post {
  id: Int!
  title: String!
  summary: String
}

type Query {
  getPosts: [Post!]!
}
```

## Mutations

To define mutations, you can either create a separate class for your mutations or include them in your root type. To mark a field as a mutation, use the `mutable=True` parameter in the `@api.field` decorator.

It's common practice to organize mutations in a separate class and pass it to the `GraphQLAPI` constructor.

```python
from graphql_api.api import GraphQLAPI

# This example is illustrative. The GraphQLAPI constructor would need to be
# updated to accept a `mutation_type`.
# api = GraphQLAPI(root_type=Query, mutation_type=Mutation)

class Mutation:
    @api.field(mutable=True)
    def create_post(self, title: str, content: str) -> Post:
        # Logic to create and save a new post...
        return Post(title=title, content=content)
```

This would create a `Mutation` type in your schema:

```graphql
type Mutation {
  createPost(title: String!, content: String!): Post!
}
```

## Enums and Interfaces

`graphql-api` also supports more advanced GraphQL types like Enums and Interfaces.

### Enums

Define enums using Python's standard `Enum` class. `graphql-api` will automatically convert them to GraphQL enums.

```python
import enum

class Episode(enum.Enum):
    NEWHOPE = 4
    EMPIRE = 5
    JEDI = 6
```

### Interfaces

Create GraphQL interfaces by decorating a class with `@api.type(interface=True)`. Other classes can then implement this interface by inheriting from it.

```python
@api.type(interface=True)
class Character:
    @api.field
    def get_id(self) -> str: ...
    @api.field
    def get_name(self) -> str: ...

class Human(Character):
    # This class will automatically have the `id` and `name` fields
    # from the Character interface.
    @api.field
    def home_planet(self) -> str:
        return "Earth"
```

This feature allows you to build flexible and maintainable schemas that adhere to GraphQL best practices. 