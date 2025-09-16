---
title: "Defining Schemas"
linkTitle: "Schema Definition"
weight: 3
description: >
  Learn how to define GraphQL schemas using decorators and type hints
---

# Defining Schemas

`graphql-api` uses a decorator-based, code-first approach to schema definition. This allows you to define your entire GraphQL schema using Python classes, methods, and type hints.

## Decorator Patterns

`graphql-api` offers two distinct patterns for defining types and fields:

### 1. Instance Decorators (Recommended for simple applications)

Create an API instance and use its decorators:

```python
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type
class User:
    @api.field
    def name(self) -> str:
        return "Alice"
```

### 2. Global Decorators (Recommended for complex applications)

Import decorators directly from the module:

```python
from graphql_api.decorators import type, field

@type
class User:
    @field
    def name(self) -> str:
        return "Alice"
```

## Choosing Between Patterns

**Use Global Decorators When:**
- Building larger applications with multiple modules
- Avoiding circular import dependencies is important
- You want to define types across different files without sharing API instances

**Use Instance Decorators When:**
- Building smaller, single-module applications
- You need multiple isolated API instances
- You want explicit control over which types belong to which API

**Important:** Stick to one pattern per project. Mixing patterns can lead to confusion and unexpected behavior.

### Circular Import Considerations

When using instance decorators, be careful about circular imports. If you have interdependent types in different modules, you may need to structure your imports carefully:

```python
# posts.py
from api import api  # This imports the shared API instance
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from users import User

@api.type
class Post:
    @api.field
    def author(self) -> 'User':  # Forward reference as string
        # Implementation here
        pass
```

Global decorators avoid this issue since they don't require importing an API instance across modules.

## Core Concepts

- **`@api.type` / `@type`**: A class decorator that marks a Python class as a GraphQL object type.
- **`@api.field` / `@field`**: A method decorator that exposes a method as a field on a GraphQL type.
- **Type Hinting**: Python type hints are used to determine the GraphQL types for fields, arguments, and return values.

## Defining Object Types

`graphql-api` supports implicit inference for object types - so you don't have to explicitly decorate most classes with `@api.type` (although you can).

An object type is automatically inferred for the following situations:

- The class is a **Pydantic model** (inherits from `BaseModel`)
- The class is a **dataclass** (decorated with `@dataclass`)
- The class has at least one field decorated with `@api.field`
- The class defines a custom mapper or is mappable by `graphql-api`

Generally you only need `@api.type` for special cases:
- Root types: `@api.type(is_root_type=True)`
- Interfaces: `@api.type(interface=True)`
- When you need to override the default behavior

### Basic Object Types

To define a GraphQL object type, simply create a Python class with fields. Here are both approaches:

**Instance Decorator Pattern:**
```python
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

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

**Global Decorator Pattern:**
```python
from graphql_api.decorators import type, field

class User:
    """Represents a user in the system."""
    @field
    def id(self) -> int:
        return 1

    @field
    def name(self) -> str:
        return "Alice"

# Create API instance and set root type
from graphql_api.api import GraphQLAPI
api = GraphQLAPI()

@type(is_root_type=True)
class Query:
    @field
    def get_user(self) -> User:
        return User()

api.root_type = Query
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

### Naming Conventions

You may have noticed that the Python method `get_user` (snake_case) was automatically converted to the GraphQL field `getUser` (camelCase). `graphql-api` handles this conversion for you to maintain standard naming conventions in both languages. If you need to override this behavior, you can provide a custom name for a field:

```python
@api.field(name="explicitlyNamedField")
def a_python_method(self) -> str:
    return "some value"
```

## Fields and Resolvers

Each method decorated with `@api.field` within a GraphQL type class becomes a field in the schema. The method itself acts as the resolver for that field.

### Field Arguments

To add arguments to a field, simply add them as parameters to the resolver method, complete with type hints.

**Instance Decorator Pattern:**
```python
@api.type(is_root_type=True)
class Query:
    @api.field
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
```

**Global Decorator Pattern:**
```python
@type(is_root_type=True)
class Query:
    @field
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

**Instance Decorator Pattern:**
```python
from typing import List, Optional

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

**Global Decorator Pattern:**
```python
from typing import List, Optional
from graphql_api.decorators import type, field

class Post:
    @field
    def id(self) -> int:
        return 123

    @field
    def title(self) -> str:
        return "My First Post"

    @field
    def summary(self) -> Optional[str]:
        return None # This field can be null

@type(is_root_type=True)
class Query:
    @field
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

## Mutations and Input Types

While simple mutations can accept scalar types as arguments, most complex mutations use **Input Types**. An input type is a special kind of object type that can be passed as an argument to a field. You can define them using Pydantic models or dataclasses, which `graphql-api` will automatically convert to `GraphQLInputObjectType`.

### Defining an Input Type

Let's define a Pydantic model to represent the input for creating a post.

```python
from pydantic import BaseModel

class CreatePostInput(BaseModel):
    title: str
    content: str
    author_email: str
```

### Using an Input Type in a Mutation

Now, you can use `CreatePostInput` as an argument in your mutation resolver. The resolver will receive an instance of the `CreatePostInput` model.

**Instance Decorator Pattern:**
```python
# In your mutations class
@api.field(mutable=True)
def create_post(self, input: CreatePostInput) -> Post:
    print(f"Creating post '{input.title}' by {input.author_email}")
    # Logic to create and save a new post...
    return Post(id=456, title=input.title, content=input.content)
```

**Global Decorator Pattern:**
```python
# In your mutations class  
@field(mutable=True)
def create_post(self, input: CreatePostInput) -> Post:
    print(f"Creating post '{input.title}' by {input.author_email}")
    # Logic to create and save a new post...
    return Post(id=456, title=input.title, content=input.content)
```

This generates a clean and organized mutation in your schema:

```graphql
input CreatePostInput {
  title: String!
  content: String!
  authorEmail: String!
}

type Mutation {
  createPost(input: CreatePostInput!): Post!
}
```

This approach is highly recommended as it makes your mutations cleaner and more extensible.

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

Create GraphQL interfaces by decorating a class with `@api.type(interface=True)` or `@type(interface=True)`. Other classes can then implement this interface by inheriting from it.

**Instance Decorator Pattern:**
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

**Global Decorator Pattern:**
```python
@type(interface=True)
class Character:
    @field
    def get_id(self) -> str: ...
    @field
    def get_name(self) -> str: ...

class Human(Character):
    # This class will automatically have the `id` and `name` fields
    # from the Character interface.
    @field
    def home_planet(self) -> str:
        return "Earth"
```

This feature allows you to build flexible and maintainable schemas that adhere to GraphQL best practices.

### Union Types

`graphql-api` can create `GraphQLUnionType`s from Python's `typing.Union`. This is useful when a field can return one of several different object types.

**Instance Decorator Pattern:**
```python
from typing import Union

# Assume Cat and Dog are Pydantic models or @api.type classes
class Cat(BaseModel):
    name: str
    meow_volume: int

class Dog(BaseModel):
    name: str
    bark_loudness: int

@api.type(is_root_type=True)
class Query:
    @api.field
    def search_pet(self, name: str) -> Union[Cat, Dog]:
        if name == "Whiskers":
            return Cat(name="Whiskers", meow_volume=10)
        if name == "Fido":
            return Dog(name="Fido", bark_loudness=100)
```

**Global Decorator Pattern:**
```python
from typing import Union

# Assume Cat and Dog are Pydantic models or @type classes
class Cat(BaseModel):
    name: str
    meow_volume: int

class Dog(BaseModel):
    name: str
    bark_loudness: int

@type(is_root_type=True)
class Query:
    @field
    def search_pet(self, name: str) -> Union[Cat, Dog]:
        if name == "Whiskers":
            return Cat(name="Whiskers", meow_volume=10)
        if name == "Fido":
            return Dog(name="Fido", bark_loudness=100)
```

To query a union type, the client must use fragment spreads to specify which fields to retrieve for each possible type.

```graphql
query {
    searchPet(name: "Whiskers") {
        ... on Cat {
            name
            meowVolume
        }
        ... on Dog {
            name
            barkLoudness
        }
    }
}
```