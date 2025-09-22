---
title: "Mutations and Input Types"
weight: 6
description: >
  Creating GraphQL mutations with input types for data modification operations
---

# Mutations and Input Types

GraphQL mutations allow clients to modify data on the server. This guide covers how to create mutations and define input types for complex data operations.

## Basic Mutations

In Mode 1 (Single Root Type), mark mutation fields with `mutable=True`:

```python
from typing import Optional

@api.type(is_root_type=True)
class Root:
    # Query fields (default behavior)
    @api.field
    def get_user(self, id: str) -> Optional[User]:
        return find_user_by_id(id)

    # Mutation fields (marked with mutable=True)
    @api.field(mutable=True)
    def create_user(self, name: str, email: str) -> User:
        """Create a new user account."""
        user = User(id=generate_id(), name=name, email=email)
        save_user(user)
        return user

    @api.field(mutable=True)
    def update_user(self, id: str, name: Optional[str] = None, email: Optional[str] = None) -> User:
        """Update an existing user's information."""
        user = find_user_by_id(id)
        if not user:
            raise ValueError(f"User with id {id} not found")

        if name is not None:
            user.name = name
        if email is not None:
            user.email = email

        save_user(user)
        return user

    @api.field(mutable=True)
    def delete_user(self, id: str) -> bool:
        """Delete a user account."""
        success = delete_user_by_id(id)
        return success
```

This generates the following GraphQL schema:

```graphql
type Query {
  getUser(id: String!): User
}

type Mutation {
  createUser(name: String!, email: String!): User!
  updateUser(id: String!, name: String, email: String): User!
  deleteUser(id: String!): Boolean!
}
```

## Input Types

For complex mutations, define input types using Pydantic models or dataclasses:

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class CreateUserInput(BaseModel):
    """Input data for creating a new user account."""
    name: str = Field(description="The user's full name")
    email: str = Field(description="Valid email address")
    age: Optional[int] = Field(description="Age in years", ge=0, le=150)
    tags: List[str] = Field(default_factory=list, description="User tags")

class UpdateUserInput(BaseModel):
    """Input data for updating user information."""
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    tags: Optional[List[str]] = None

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def create_user(self, input: CreateUserInput) -> User:
        """Create a new user with the provided information."""
        user = User(
            id=generate_id(),
            name=input.name,
            email=input.email,
            age=input.age,
            tags=input.tags
        )
        save_user(user)
        return user

    @api.field(mutable=True)
    def update_user(self, id: str, input: UpdateUserInput) -> User:
        """Update a user's information."""
        user = find_user_by_id(id)
        if not user:
            raise ValueError(f"User with id {id} not found")

        # Only update fields that are provided
        if input.name is not None:
            user.name = input.name
        if input.email is not None:
            user.email = input.email
        if input.age is not None:
            user.age = input.age
        if input.tags is not None:
            user.tags = input.tags

        save_user(user)
        return user
```

This generates GraphQL input types:

```graphql
input CreateUserInput {
  """The user's full name"""
  name: String!

  """Valid email address"""
  email: String!

  """Age in years"""
  age: Int

  """User tags"""
  tags: [String!]!
}

input UpdateUserInput {
  name: String
  email: String
  age: Int
  tags: [String!]
}

type Mutation {
  """Create a new user with the provided information."""
  createUser(input: CreateUserInput!): User!

  """Update a user's information."""
  updateUser(id: String!, input: UpdateUserInput!): User!
}
```

## Dataclass Input Types

You can also use dataclasses for input types:

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class CreatePostInput:
    """Input for creating a new blog post."""
    title: str
    content: str
    author_id: int
    tags: List[str] = None
    published: bool = False

@dataclass
class UpdatePostInput:
    """Input for updating an existing blog post."""
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    published: Optional[bool] = None

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def create_post(self, input: CreatePostInput) -> Post:
        """Create a new blog post."""
        post = Post(
            id=generate_id(),
            title=input.title,
            content=input.content,
            author_id=input.author_id,
            tags=input.tags or [],
            published=input.published,
            created_at=datetime.now()
        )
        save_post(post)
        return post
```

## Nested Input Types

Input types can contain other input types for complex data structures:

```python
from pydantic import BaseModel

class AddressInput(BaseModel):
    """Address information input."""
    street: str
    city: str
    country: str
    postal_code: Optional[str] = None

class CreateCompanyInput(BaseModel):
    """Input for creating a company."""
    name: str
    description: Optional[str] = None
    address: AddressInput
    contact_email: str

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def create_company(self, input: CreateCompanyInput) -> Company:
        """Create a new company with address information."""
        company = Company(
            id=generate_id(),
            name=input.name,
            description=input.description,
            address=Address(
                street=input.address.street,
                city=input.address.city,
                country=input.address.country,
                postal_code=input.address.postal_code
            ),
            contact_email=input.contact_email
        )
        save_company(company)
        return company
```

## Validation and Error Handling

Use Pydantic's built-in validation for input types:

```python
from pydantic import BaseModel, Field, validator, EmailStr

class CreateUserInput(BaseModel):
    """Input for creating a new user with validation."""
    name: str = Field(min_length=2, max_length=50)
    email: EmailStr
    age: int = Field(ge=13, le=120)  # Age between 13 and 120
    password: str = Field(min_length=8)

    @validator('name')
    def name_must_contain_space(cls, v):
        if ' ' not in v:
            raise ValueError('Name must contain at least one space')
        return v

    @validator('password')
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def create_user(self, input: CreateUserInput) -> User:
        """Create a new user with validation."""
        # Pydantic validation happens automatically
        # If validation fails, a GraphQL error is returned

        user = User(
            id=generate_id(),
            name=input.name,
            email=input.email,
            age=input.age,
            password_hash=hash_password(input.password)
        )
        save_user(user)
        return user
```

## Batch Operations

Handle multiple operations in a single mutation:

```python
from typing import List

class DeleteUsersInput(BaseModel):
    """Input for deleting multiple users."""
    user_ids: List[str] = Field(description="List of user IDs to delete")

class BulkUserResult(BaseModel):
    """Result of bulk user operations."""
    success_count: int
    failed_count: int
    errors: List[str]

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def delete_users(self, input: DeleteUsersInput) -> BulkUserResult:
        """Delete multiple users in a single operation."""
        success_count = 0
        failed_count = 0
        errors = []

        for user_id in input.user_ids:
            try:
                delete_user_by_id(user_id)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to delete user {user_id}: {str(e)}")

        return BulkUserResult(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors
        )
```

## Mode 2: Explicit Mutation Types

If using Mode 2 (Explicit Types), define a separate Mutation class:

```python
@api.type
class Query:
    @api.field
    def users(self) -> List[User]:
        return get_all_users()

@api.type
class Mutation:
    @api.field
    def create_user(self, input: CreateUserInput) -> User:
        # Implementation here
        pass

    @api.field
    def update_user(self, id: str, input: UpdateUserInput) -> User:
        # Implementation here
        pass

# Assign the types to the API
api.query_type = Query
api.mutation_type = Mutation
```

## Using Mutations

Clients can execute mutations using GraphQL mutation operations:

```graphql
mutation CreateUser {
  createUser(input: {
    name: "Alice Smith"
    email: "alice@example.com"
    age: 30
    tags: ["developer", "python"]
  }) {
    id
    name
    email
    createdAt
  }
}

mutation UpdateUser {
  updateUser(
    id: "123"
    input: {
      name: "Alice Johnson"
      tags: ["developer", "python", "graphql"]
    }
  ) {
    id
    name
    email
    tags
  }
}
```

## Best Practices

**Use descriptive input types:**
```python
# ✅ Good: Specific, clear purpose
class CreateBlogPostInput(BaseModel):
    title: str
    content: str
    author_id: str

# ❌ Avoid: Generic, unclear purpose
class PostInput(BaseModel):
    title: str
    content: str
```

**Validate input data:**
```python
class CreateOrderInput(BaseModel):
    items: List[OrderItemInput] = Field(min_items=1)
    customer_id: str

    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('Order must contain at least one item')
        return v
```

**Return meaningful results:**
```python
# ✅ Good: Return the created/updated object
@api.field(mutable=True)
def create_user(self, input: CreateUserInput) -> User:
    user = create_new_user(input)
    return user  # Client can query any fields they need

# ❌ Avoid: Just returning success/failure
@api.field(mutable=True)
def create_user(self, input: CreateUserInput) -> bool:
    create_new_user(input)
    return True  # Client gets no useful information
```

This foundation gives you everything needed to build robust GraphQL mutations with proper input validation and error handling.

## Next Areas

With mutations working, you can explore:

**Advanced type modeling:** [Enums & Interfaces](enums-interfaces/) covers polymorphism and sophisticated type relationships.

**Production concerns:** [Error Handling](error-handling/) provides comprehensive error management strategies.

**Integration:** [Pydantic & Dataclasses](pydantic-and-dataclasses/) shows how to integrate with validation libraries.