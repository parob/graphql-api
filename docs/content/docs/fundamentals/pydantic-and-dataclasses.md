---
title: "Pydantic & Dataclasses"
weight: 8
description: >
  Integrate Pydantic models and dataclasses into your GraphQL schema
---

# Using Pydantic and Dataclasses

`graphql-api` provides first-class support for Pydantic and dataclasses, allowing you to use them seamlessly as GraphQL types. This is a powerful feature that helps you build robust, self-documenting, and validated APIs with minimal boilerplate.

## Pydantic Integration

Pydantic models are automatically converted into GraphQL object types. This is ideal for defining the structure of your data and ensuring type safety.

### Defining Pydantic Types

To use a Pydantic model in your schema, simply define it as you normally would and use it as a type hint in your resolvers.

```python
from pydantic import BaseModel
from typing import List
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

class Author(BaseModel):
    name: str

class Book(BaseModel):
    title: str
    author: Author

@api.type(is_root_type=True)
class Query:
    @api.field
    def get_book(self) -> Book:
        return Book(
            title="The Hitchhiker's Guide to the Galaxy",
            author=Author(name="Douglas Adams")
        )
```

This will generate the following GraphQL schema:

```graphql
type Author {
  name: String!
}

type Book {
  title: String!
  author: Author!
}

type Query {
  getBook: Book!
}
```

### Pydantic Fields and Validation

All Pydantic features, such as field descriptions, default values, and aliases, are respected and reflected in the generated schema.

```python
from pydantic import BaseModel, Field
from typing import Optional

class UserProfile(BaseModel):
    username: str
    age: Optional[int] = Field(None, description="The user's age")
    is_active: bool = True
```

This will be converted to:

```graphql
type UserProfile {
  username: String!
  "The user's age"
  age: Int
  isActive: Boolean!
}
```

#### Field Aliases

Pydantic's field aliases are fully supported. This is useful when your data source uses a different naming convention (e.g., snake_case in your database) than your GraphQL schema (camelCase).

```python
from pydantic import BaseModel, Field

class Task(BaseModel):
    id: int
    # The data source uses `task_name`, but the API will expose `taskName`.
    task_name: str = Field(..., alias="taskName")
    is_completed: bool = Field(False, alias="isCompleted")

    class Config:
        # This allows you to create a Task instance using the alias names.
        populate_by_name = True
```

When you return a `Task` object, `graphql-api` will use the alias in the schema, but you can populate it using the Python-friendly field name.

### Recursive Models

Pydantic models can be recursive, and `graphql-api` will handle the conversion to a recursive GraphQL type correctly. This is useful for modeling hierarchical data like organizational charts or comment threads.

```python
from typing import Optional
from pydantic import BaseModel

class Employee(BaseModel):
    name: str
    manager: Optional['Employee'] = None

# For older versions of Pydantic, you may need to call this to update the forward reference.
# Employee.model_rebuild()

@api.type(is_root_type=True)
class Query:
    @api.field
    def get_employee_hierarchy(self) -> Employee:
        manager = Employee(name="Big Boss")
        return Employee(name="Direct Report", manager=manager)
```

This generates a self-referencing `Employee` type in GraphQL:

```graphql
type Employee {
  name: String!
  manager: Employee
}
```

## Dataclass Integration

Similar to Pydantic, standard Python dataclasses can also be used to define your GraphQL types.

### Defining Dataclass Types

Decorate a class with `@dataclass` and use it as a type hint in your resolvers.

```python
from dataclasses import dataclass, field
from typing import List
from graphql_api.api import GraphQLAPI

api = GraphQLAPI()

@dataclass
class Product:
    id: int
    name: str
    in_stock: bool = True

@api.type(is_root_type=True)
class Query:
    @api.field
    def get_featured_products(self) -> List[Product]:
        return [
            Product(id=1, name="Laptop"),
            Product(id=2, name="Mouse", in_stock=False),
        ]
```

This generates the following schema:

```graphql
type Product {
  id: Int!
  name: String!
  inStock: Boolean!
}

type Query {
  getFeaturedProducts: [Product!]!
}
```

By leveraging Pydantic and dataclasses, you can create clean, maintainable, and robust GraphQL APIs, letting `graphql-api` handle the conversion to the GraphQL schema.