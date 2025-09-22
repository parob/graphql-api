---
title: "Defining Schemas"
weight: 2
description: >
  Learn how to define GraphQL schemas using decorators and type hints
---

# Defining Schemas

`graphql-api` uses a decorator-based, code-first approach to schema definition. This allows you to define your entire GraphQL schema using Python classes, methods, and type hints.

## Decorator Patterns

`graphql-api` offers two distinct patterns for defining types and fields:

### 1. Instance Decorators (Recommended)

Create an API instance and use its decorators - this is the preferred approach:

```python
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type
class User:
    @api.field
    def name(self) -> str:
        return "Alice"
```

### 2. Global Decorators (Use only when necessary)

Import decorators directly from the module - only use this to avoid circular imports:

```python
from graphql_api.decorators import type, field

@type
class User:
    @field
    def name(self) -> str:
        return "Alice"
```

## Choosing Between Patterns

**Use Instance Decorators (Recommended):**
- **Better isolation**: Each API instance has its own isolated types and fields
- **Explicit control**: Clear ownership of types within specific API instances
- **Type safety**: Better IDE support and type checking
- **Multiple APIs**: Ability to create separate API instances for different purposes
- **Cleaner architecture**: More explicit and maintainable code structure

**Use Global Decorators only when:**
- You encounter circular import issues with instance decorators
- You need to define types across modules where sharing an API instance is problematic

**Important:** Always prefer instance decorators unless you specifically need to avoid circular imports. Stick to one pattern per project.

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

## Schema Definition Modes

`graphql-api` offers two distinct approaches for organizing your GraphQL operations (queries, mutations, subscriptions):

### Mode 1: Single Root Type (Strongly Recommended)

In this mode, you define all operations in a single root class. This is the **preferred approach** for most applications as it allows your GraphQL API to be used more like a normal application:

```python
from typing import AsyncGenerator
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type(is_root_type=True)
class Root:
    # Query field
    @api.field
    def get_user(self, user_id: int) -> User:
        return get_user_from_db(user_id)

    # Mutation field - marked with mutable=True
    @api.field(mutable=True)
    def update_user(self, user_id: int, name: str) -> User:
        return update_user_in_db(user_id, name)

    # Subscription field - automatically detected by AsyncGenerator return type
    @api.field
    async def on_user_updated(self, user_id: int) -> AsyncGenerator[User, None]:
        """Real-time user updates"""
        while True:
            await asyncio.sleep(1)
            yield get_user_from_db(user_id)

# Create API instance with the root type
api_with_root = GraphQLAPI(root_type=Root)
```

**Advantages:**
- **Natural application structure**: Operations are co-located like in a normal application
- **Automatic operation type detection**: No need to explicitly categorize operations
- **Simplified development**: All operations accessible from a single entry point
- **Less boilerplate**: Minimal setup required
- **Better for most use cases**: Works like a traditional application with a single API surface

**Use when:**
- Building any size application (recommended as the default choice)
- You want your GraphQL API to feel like a normal application
- You prefer co-location of related functionality
- You want automatic operation type detection

### Mode 2: Explicit Types

For more complex applications, you can define separate classes for queries, mutations, and subscriptions:

```python
from typing import AsyncGenerator
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@api.type
class Query:
    @api.field
    def get_user(self, user_id: int) -> User:
        return get_user_from_db(user_id)

    @api.field
    def list_posts(self) -> List[Post]:
        return get_all_posts()

@api.type
class Mutation:
    @api.field
    def update_user(self, user_id: int, name: str) -> User:
        return update_user_in_db(user_id, name)

    @api.field
    def create_post(self, input: CreatePostInput) -> Post:
        return create_new_post(input)

@api.type
class Subscription:
    @api.field
    async def on_user_updated(self, user_id: int) -> AsyncGenerator[User, None]:
        """Real-time user updates"""
        while True:
            await asyncio.sleep(1)
            yield get_user_from_db(user_id)

# Create API instance and set explicit types
api_explicit = GraphQLAPI()
api_explicit.query_type = Query
api_explicit.mutation_type = Mutation
api_explicit.subscription_type = Subscription
```

**Advantages:**
- Clear separation of concerns
- Better organization for large schemas
- Easier to maintain in teams
- Explicit control over operation types

**Use when:**
- You have a very specific architectural requirement for operation separation
- Working with very large teams where explicit boundaries are helpful
- Migrating from other GraphQL frameworks that use this pattern
- You need maximum control over schema organization

### Choosing the Right Mode

**Use Mode 1 (Single Root Type) for:**
- **Most applications** (recommended default choice)
- Any size application where you want natural application structure
- When you want your API to feel like a normal application
- Better development experience with co-located operations

**Use Mode 2 (Explicit Types) only when:**
- You have specific architectural constraints requiring operation separation
- Working with very large teams that benefit from explicit boundaries
- You're migrating from other GraphQL frameworks and need compatibility
- You have complex requirements that specifically benefit from separation

Both modes are fully supported and can be mixed within the same application if needed (though this is not recommended for consistency).

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
- **Root types**: `@api.type(is_root_type=True)` - Required for the main query/mutation/subscription entry point
- **Interfaces**: `@api.type(interface=True)` - Required to define GraphQL interfaces
- **Explicit types mode**: When using Mode 2, you need `@api.type` to register classes with the API instance
- **When you need to override the default behavior** or add metadata

**Important**: If you use instance decorators (`@api.field`), you usually don't need `@api.type` unless it's a root type or interface. The type will be automatically inferred and registered.

### Basic Object Types

To define a GraphQL object type, simply create a Python class with fields. The preferred approach uses instance decorators:

**Instance Decorator Pattern (Recommended):**
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

**Global Decorator Pattern (Only if needed for circular imports):**
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

**Instance Decorator Pattern (Recommended):**
```python
@api.type(is_root_type=True)
class Query:
    @api.field
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
```

**Global Decorator Pattern (Only if needed for circular imports):**
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

**Instance Decorator Pattern (Recommended):**
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

**Global Decorator Pattern (Only if needed for circular imports):**
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

**Instance Decorator Pattern (Recommended):**
```python
# In your mutations class
@api.field(mutable=True)
def create_post(self, input: CreatePostInput) -> Post:
    print(f"Creating post '{input.title}' by {input.author_email}")
    # Logic to create and save a new post...
    return Post(id=456, title=input.title, content=input.content)
```

**Global Decorator Pattern (Only if needed for circular imports):**
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

### Marking Fields as Mutations

When using Mode 1 (Single Root Type), you must explicitly mark mutation fields with `mutable=True`:

```python
@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def create_post(self, input: CreatePostInput) -> Post:
        return create_new_post(input)
```

When using Mode 2 (Explicit Types), all fields in a `Mutation` class are automatically treated as mutations:

```python
@api.type
class Mutation:
    @api.field
    def create_post(self, input: CreatePostInput) -> Post:
        return create_new_post(input)  # Automatically a mutation
```

## Enums and Interfaces

For more advanced GraphQL type definitions including enums and interfaces, see the dedicated [Enums and Interfaces](../enums-interfaces/) documentation.

## Field Types

`graphql-api` supports a wide range of Python types and automatically maps them to appropriate GraphQL types. For a comprehensive guide to all supported types including scalars, collections, enums, custom types, and more, see the dedicated [Field Types](../field-types/) documentation.

**Quick overview of supported types:**
- Built-in scalars: `str`, `int`, `float`, `bool`, `UUID`, `datetime`, `date`, `bytes`
- Collections: `List[T]`, `Optional[T]`, nested types
- JSON types: `dict`, `list`, `JsonType`
- Enums: Python `enum.Enum` classes
- Custom scalars: Define your own GraphQL scalar types
- Object types: Dataclasses, Pydantic models, custom classes
- Union types: `typing.Union` for multiple return types

## Union Types

`graphql-api` can create `GraphQLUnionType`s from Python's `typing.Union`. This is useful when a field can return one of several different object types.

**Instance Decorator Pattern (Recommended):**
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

**Global Decorator Pattern (Only if needed for circular imports):**
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

## Related Topics

Now that you understand schema definition fundamentals, explore these related areas:

**Type system:** [Field Types](field-types/) covers all supported scalar and collection types in detail.

**Advanced schemas:**
- [Object Types & Relationships](object-types/) - Complex interconnected types
- [Enums & Interfaces](enums-interfaces/) - Advanced type modeling

**Building applications:** [Input Types & Mutations](mutations/) shows how to handle data modifications and validation.